"""Public job fixtures, Google targets and transport failures without live requests."""

import gzip
import json
import socket
from urllib.parse import quote

import pytest
from fastapi import HTTPException

from backend.services import job_service

JOB_URL = "https://jobs.example.com/job/123"
DESCRIPTION = "<p>Build accessible interfaces and maintain reliable software.</p><p>Apply to hiring@example.com.</p>"


def script(value, *, kind="application/ld+json", identifier=""):
    return f'<script type="{kind}" id="{identifier}">{json.dumps(value)}</script>'


def posting(**overrides):
    return {
        "@type": ["Thing", "https://schema.org/JobPosting"],
        "title": "Frontend Developer",
        "hiringOrganization": {"name": "Example Employer"},
        "description": DESCRIPTION,
        **overrides,
    }


def page(monkeypatch, html, url=JOB_URL):
    monkeypatch.setattr(job_service, "fetch_page", lambda value: (html, value))
    return job_service.import_job(url)


def test_jsonld_graph_chooses_the_requested_job_not_the_first_recommendation(monkeypatch):
    html = script(
        {
            "@graph": [
                posting(title="Other job", url="https://jobs.example.com/job/999"),
                posting(url=JOB_URL),
            ]
        }
    )
    result = page(monkeypatch, html, JOB_URL + "?utm_source=google")
    assert result["title"] == "Frontend Developer"
    assert result["company"] == "Example Employer"
    assert result["email"] == "hiring@example.com"
    assert result["method"] == "JobPosting" and result["needs_review"] is True


def test_multiple_jobs_without_a_selected_target_are_not_silently_imported(monkeypatch):
    html = script([posting(title="One job"), posting(title="Another job")])
    with pytest.raises(HTTPException, match="mehrere Stellen"):
        page(monkeypatch, html)


def test_jsonld_employer_reference_uses_only_the_explicit_hiring_organization(monkeypatch):
    html = script(
        {
            "@graph": [
                {"@type": "Organization", "@id": "#publisher", "name": "The job portal"},
                {"@type": "Organization", "@id": "#employer", "name": "Actual employer"},
                posting(hiringOrganization={"@id": "#employer"}),
            ]
        }
    )
    assert page(monkeypatch, html)["company"] == "Actual employer"
    assert (
        page(monkeypatch, script(posting(hiringOrganization="https://example.com")))["company"]
        == ""
    )


def test_next_data_imports_the_job_and_explicit_sibling_company(monkeypatch):
    html = script(
        {
            "props": {
                "pageProps": {
                    "company": {"name": "Explicit Company"},
                    "job": {
                        "title": "Operations Manager",
                        "description": "<p>Coordinate service teams and prepare weekly operational plans.</p>",
                        "requirements": ["Relevant experience", "Clear communication"],
                        "benefits": "Training and a predictable schedule",
                    },
                }
            }
        },
        kind="application/json",
        identifier="__NEXT_DATA__",
    )
    result = page(monkeypatch, html)
    assert result["title"] == "Operations Manager"
    assert result["company"] == "Explicit Company"
    assert "Relevant experience" in result["description"]
    assert "Training and a predictable schedule" in result["description"]
    assert result["method"] == "EmbeddedJSON"


def test_indeed_embedded_job_info_can_be_read_when_publicly_available(monkeypatch):
    html = script(
        {
            "jobInfoWrapperModel": {
                "jobInfoModel": {
                    "jobTitle": "Cook",
                    "companyName": "Kitchen Example",
                    "sanitizedJobDescription": "<p>Prepare seasonal meals and keep the kitchen organized.</p>",
                }
            }
        },
        kind="application/json",
    )
    result = page(monkeypatch, html, "https://de.indeed.com/viewjob?jk=fixture")
    assert result["title"] == "Cook" and result["company"] == "Kitchen Example"
    assert result["provider"] == "Indeed"


def test_initial_state_json_is_read_without_evaluating_script(monkeypatch):
    state = {
        "job": {
            "jobTitle": "Engineer",
            "jobDescription": "Create and review reliable technical designs with the team.",
            "companyName": "Company",
        }
    }
    html = "<script>window.__INITIAL_STATE__ = " + json.dumps(state) + ";</script>"
    result = page(monkeypatch, html)
    assert result["method"] == "EmbeddedJSON"
    assert result["title"] == "Engineer"
    invalid = (
        "<script>window.__INITIAL_STATE__ = "
        + json.dumps(state)
        + "; window.runAnything();</script>"
    )
    with pytest.raises(HTTPException, match="Kein vollständiger Stellentext"):
        page(monkeypatch, invalid)


def test_job_section_excludes_navigation_cookie_text_and_related_jobs(monkeypatch):
    html = (
        "<header>Cookie settings. Contact privacy@example.com.</header><main><h1>Frontend <span>Developer</span></h1><div id='jobDescriptionText'>"
        + DESCRIPTION
        + "</div><aside><h1>Other jobs</h1><p>Unrelated employer and job.</p></aside></main><footer>Portal owner.</footer>"
    )
    result = page(monkeypatch, html)
    assert (
        result["description"]
        == "Build accessible interfaces and maintain reliable software.\nApply to hiring@example.com."
    )
    assert result["email"] == "hiring@example.com" and result["company"] == ""
    assert result["method"] == "HTML-JobSection"
    assert "Unrelated" not in result["description"]


def test_stepstone_sections_are_kept_in_order_without_sidebar_content(monkeypatch):
    html = "<h1>Service Manager</h1><div data-at='section-text-introduction'><p>A team serving customers with reliable processes.</p></div><div data-at='section-text-description'><ul><li>Coordinate service colleagues.</li></ul></div><div data-at='section-text-profile'><p>Relevant service experience.</p></div><aside>Related jobs and unrelated tasks.</aside>"
    result = page(
        monkeypatch,
        html,
        "https://www.stepstone.de/stellenangebote--Service-Manager--123-inline.html",
    )
    assert result["provider"] == "StepStone" and result["method"] == "HTML-JobSection"
    assert result["description"].index("Coordinate") < result["description"].index("Relevant")
    assert "unrelated" not in result["description"]


def test_google_redirect_url_resolves_to_the_original_posting(monkeypatch):
    target = JOB_URL + "?id=42"
    google = "https://www.google.de/url?url=" + quote(target, safe="")
    received = []
    monkeypatch.setattr(
        job_service, "fetch_page", lambda url: (received.append(url) or script(posting()), url)
    )
    result = job_service.import_job(google)
    assert received == [target]
    assert result["url"] == target and result["resolved_from"] == google


def test_indeed_selected_job_in_search_url_is_normalized_without_choosing_a_card(monkeypatch):
    selected = "https://de.indeed.com/jobs?q=Cook&vjk=a722eef44a5f75b2"
    received = []
    monkeypatch.setattr(
        job_service, "fetch_page", lambda url: (received.append(url) or script(posting()), url)
    )
    result = job_service.import_job(selected)
    assert received == ["https://de.indeed.com/viewjob?jk=a722eef44a5f75b2"]
    assert result["resolved_from"] == selected
    assert result["provider"] == "Indeed"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/search?q=jobs&ibp=htl;jobs#htidocid=opaque",
        "https://www.google.de/url?q=not-a-job-url",
        "https://www.google.al/",
    ],
)
def test_google_search_or_opaque_job_id_requires_the_original_job_link(monkeypatch, url):
    monkeypatch.setattr(
        job_service, "fetch_page", lambda _: pytest.fail("Must not fetch a search page")
    )
    with pytest.raises(HTTPException, match="Bewerben auf"):
        job_service.import_job(url)


def test_one_canonical_target_is_read_and_loops_are_bounded(monkeypatch):
    wrapper = "https://jobs.example.com/share/123"
    received = []

    def fetch(url):
        received.append(url)
        return (
            f'<link rel="canonical" href="{JOB_URL}">' if url == wrapper else script(posting())
        ), url

    monkeypatch.setattr(job_service, "fetch_page", fetch)
    assert job_service.import_job(wrapper)["url"] == JOB_URL
    assert received == [wrapper, JOB_URL]
    received.clear()
    monkeypatch.setattr(
        job_service,
        "fetch_page",
        lambda url: (
            received.append(url)
            or f'<link rel="canonical" href="{JOB_URL if url == wrapper else wrapper}">',
            url,
        ),
    )
    with pytest.raises(HTTPException, match="Kein vollständiger Stellentext"):
        job_service.import_job(wrapper)
    assert len(received) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://de.indeed.com/jobs?q=Cook",
        "https://www.stepstone.de/jobs/engineer",
        "https://join.com/companies/example",
    ],
)
def test_known_search_and_company_pages_do_not_become_job_descriptions(monkeypatch, url):
    with pytest.raises(HTTPException, match="Such- oder Firmenseite"):
        page(
            monkeypatch,
            "<h1>Open positions</h1><p>A list of many available jobs and employers.</p>",
            url,
        )


def test_human_verification_page_does_not_become_a_job(monkeypatch):
    html = (
        "<title>Authenticating...</title><h1>Verify you are human</h1><p>Please complete the browser verification to continue.</p>"
        + script(posting())
    )
    with pytest.raises(HTTPException, match="Zugriffskontrolle"):
        page(monkeypatch, html, "https://de.indeed.com/viewjob?jk=fixture")
    # A legitimate application page can use CAPTCHA on its form; it is not a challenge page.
    result = page(monkeypatch, "<h1>Engineer</h1>" + script(posting()) + "<form>captcha</form>")
    assert result["method"] == "JobPosting"


class Response:
    def __init__(self, data=b"", status=200, headers=None):
        self.data, self.status, self.offset = data, status, 0
        self.headers = {"Content-Type": "text/html; charset=utf-8", **(headers or {})}

    def getheader(self, name, default=""):
        return self.headers.get(name, default)

    def read1(self, amount):
        part = self.data[self.offset : self.offset + amount]
        self.offset += len(part)
        return part


def transport(monkeypatch, responses):
    made = []

    def resolve(host, *_, **__):
        address = "127.0.0.1" if host == "private.example.com" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    class Connection:
        sock = None

        def __init__(self, host, address, timeout):
            self.closed = False
            self.host, self.address = host, address
            made.append(self)
            self.response = next(responses)

        def request(self, method, path, headers):
            assert method == "GET" and "Authorization" not in headers and "Cookie" not in headers

        def getresponse(self):
            return self.response

        def close(self):
            self.closed = True

    monkeypatch.setattr(job_service.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(job_service, "PinnedHTTPSConnection", Connection)
    return made


@pytest.mark.parametrize("status", [401, 403, 429])
def test_http_access_restrictions_offer_text_instead_of_bypass(monkeypatch, status):
    made = transport(monkeypatch, iter([Response(status=status)]))
    with pytest.raises(HTTPException, match="automatischen Abruf"):
        job_service.import_job("https://de.indeed.com/viewjob?jk=fixture")
    assert len(made) == 1 and made[0].closed


@pytest.mark.parametrize("status", [404, 410])
def test_expired_link_is_explained(monkeypatch, status):
    transport(monkeypatch, iter([Response(status=status)]))
    with pytest.raises(HTTPException, match="nicht mehr verfügbar"):
        job_service.import_job("https://join.com/companies/example/123-title")


def test_gzip_html_is_decoded_with_both_compressed_and_uncompressed_limits(monkeypatch):
    html = script(posting(title="München Engineer")).encode()
    transport(
        monkeypatch, iter([Response(gzip.compress(html), headers={"Content-Encoding": "gzip"})])
    )
    assert job_service.import_job(JOB_URL)["title"] == "München Engineer"
    bomb = gzip.compress(b"a" * (job_service.MAX_PAGE_BYTES + 1))
    made = transport(monkeypatch, iter([Response(bomb, headers={"Content-Encoding": "gzip"})]))
    with pytest.raises(HTTPException) as error:
        job_service.fetch_page(JOB_URL)
    assert error.value.status_code == 413 and made[0].closed


def test_declared_windows_charset_preserves_job_text(monkeypatch):
    html = "<h1>Köchin</h1><div id='job-description'>Für Gäste kochen und frische Gerichte vorbereiten.</div>".encode(
        "cp1252"
    )
    transport(
        monkeypatch,
        iter([Response(html, headers={"Content-Type": "text/html; charset=windows-1252"})]),
    )
    result = job_service.import_job(JOB_URL)
    assert result["title"] == "Köchin" and "Für Gäste" in result["description"]


def test_unicode_job_urls_use_idna_hosts_and_encoded_request_paths(monkeypatch):
    hosts = []
    monkeypatch.setattr(
        job_service.socket,
        "getaddrinfo",
        lambda host, *_, **__: (
            hosts.append(host)
            or [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        ),
    )
    host, address, path = job_service.public_address(
        "https://bücher.example/jobs/Köchin?ort=München"
    )
    assert host == "xn--bcher-kva.example" and hosts == [host]
    assert address == "93.184.216.34"
    assert path == "/jobs/K%C3%B6chin?ort=M%C3%BCnchen"


def test_canonical_target_cannot_fetch_private_host(monkeypatch):
    html = b'<link rel="canonical" href="https://private.example.com/job">'
    made = transport(monkeypatch, iter([Response(html)]))
    with pytest.raises(HTTPException, match="Private/interne"):
        job_service.import_job(JOB_URL)
    assert len(made) == 1 and made[0].closed


def test_google_embedded_target_cannot_fetch_private_host(monkeypatch):
    made = transport(monkeypatch, iter([]))
    url = "https://www.google.com/url?url=" + quote("https://private.example.com/job", safe="")
    with pytest.raises(HTTPException, match="Private/interne"):
        job_service.import_job(url)
    assert not made


def test_redirect_count_is_bounded_and_every_connection_closes(monkeypatch):
    made = transport(
        monkeypatch, iter([Response(status=302, headers={"Location": "/again"}) for _ in range(4)])
    )
    with pytest.raises(HTTPException, match="Weiterleitungen"):
        job_service.fetch_page(JOB_URL)
    assert len(made) == 4 and all(connection.closed for connection in made)


def test_invalid_urls_fail_before_network(monkeypatch):
    monkeypatch.setattr(
        job_service.socket, "getaddrinfo", lambda *_, **__: pytest.fail("No DNS expected")
    )
    for url in [
        "https://name:password@example.com/job",
        "https://[invalid/job",
        "https://example.com:9000/job",
        "https://example.com/job\nHeader:injected",
        "http://example.com/job",
    ]:
        with pytest.raises(HTTPException):
            job_service.import_job(url)


def test_mixed_public_and_private_dns_answers_are_rejected_before_connect(monkeypatch):
    monkeypatch.setattr(
        job_service.socket,
        "getaddrinfo",
        lambda *_, **__: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
        ],
    )
    monkeypatch.setattr(
        job_service, "PinnedHTTPSConnection", lambda *_, **__: pytest.fail("No internal connection")
    )
    with pytest.raises(HTTPException, match="Private/interne"):
        job_service.fetch_page(JOB_URL)


def test_broken_compression_does_not_return_partial_job_content(monkeypatch):
    data = gzip.compress(script(posting()).encode())[:-8]
    transport(monkeypatch, iter([Response(data, headers={"Content-Encoding": "gzip"})]))
    with pytest.raises(HTTPException, match="unvollständige Daten"):
        job_service.fetch_page(JOB_URL)


def test_http_redirect_cannot_downgrade_to_plain_http(monkeypatch):
    made = transport(
        monkeypatch,
        iter([Response(status=302, headers={"Location": "http://jobs.example.com/job"})]),
    )
    with pytest.raises(HTTPException, match="HTTPS-Stellenlinks"):
        job_service.fetch_page(JOB_URL)
    assert len(made) == 1 and made[0].closed


def test_import_route_requires_an_account_and_keeps_existing_request_limit(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.config import get_settings
    from backend.main import app
    from backend.tests.test_platform import register

    monkeypatch.setattr(get_settings(), "hosted_ai_enabled", True)
    fetched = []
    monkeypatch.setattr(
        job_service, "fetch_page", lambda url: (fetched.append(url) or script(posting()), url)
    )
    client = TestClient(app)
    assert client.post("/api/job/import", json={"url": JOB_URL}).status_code == 401
    assert not fetched
    register(client)
    for _ in range(60):
        response = client.post("/api/job/import", json={"url": JOB_URL})
        assert response.status_code == 200, response.text
    limited = client.post("/api/job/import", json={"url": JOB_URL})
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "60"
    assert len(fetched) == 60
