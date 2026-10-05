"""Bounded public HTTPS importer with DNS pinning and redirect validation."""

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import zlib
from html.parser import HTMLParser
from itertools import islice
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse

import certifi
from fastapi import HTTPException

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_STATE_BYTES = 1024 * 1024
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "section", "article"}
IGNORED_TAGS = {
    "script",
    "style",
    "head",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "noscript",
    "svg",
}
GOOGLE_DOMAINS = {
    "google.com",
    "google.de",
    "google.al",
    "google.at",
    "google.ch",
    "google.co.uk",
    "google.fr",
    "google.it",
    "google.es",
    "google.nl",
    "google.be",
    "google.ie",
    "google.ca",
    "google.com.au",
}


def _text(parts):
    return "\n".join(
        re.sub(r"[ \t\r\f\v\u00a0]+", " ", line).strip()
        for line in "".join(parts).splitlines()
        if line.strip()
    )


def _description_tag(attrs):
    labels = " ".join(
        str(attrs.get(key, "")) for key in ("id", "class", "data-testid", "data-at", "itemprop")
    ).lower()
    return bool(
        re.search(
            r"job[-_ ]?description|job[-_ ]?(?:ad[-_ ]?content|details[-_ ]?content)|vacancy[-_ ]?description",
            labels,
        )
        or re.search(
            r"section-text-(?:introduction|description|profile|benefits|additional-information)",
            labels,
        )
        or attrs.get("itemprop", "").lower() == "description"
    )


class TextParser(HTMLParser):
    """Read public data only; never evaluate scripts, forms or browser state."""

    def __init__(self):
        super().__init__()
        self.parts, self.scripts, self.states, self.frames = [], [], [], []
        self.headings, self.fragments, self.main_parts = [], [], []
        self.page_title, self.canonical, self.meta = "", "", {}
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonical = attrs.get("href", "")[:2000]
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", "")).lower()] = attrs.get(
                "content", ""
            )
        ignored = any(frame["ignored"] for frame in self.frames)
        if tag == "script":
            kind = attrs.get("type", "").lower().split(";", 1)[0].strip()
            self.script = {"kind": kind, "id": attrs.get("id", ""), "parts": []}
        if tag in BLOCK_TAGS and not ignored:
            self._append("\n")
        if tag in VOID_TAGS:
            return
        if len(self.frames) >= 256:
            raise ValueError("HTML nesting limit")
        self.frames.append(
            {
                "tag": tag,
                "ignored": tag in IGNORED_TAGS
                or "hidden" in attrs
                or attrs.get("aria-hidden") == "true",
                "heading": [] if tag == "h1" and not ignored else None,
                "title": [] if tag == "title" else None,
                "fragment": []
                if not ignored
                and _description_tag(attrs)
                and not any(frame["fragment"] is not None for frame in self.frames)
                else None,
                "main": tag in {"main", "article"},
            }
        )

    def handle_endtag(self, tag):
        index = next(
            (i for i in range(len(self.frames) - 1, -1, -1) if self.frames[i]["tag"] == tag), None
        )
        if index is not None:
            for frame in self.frames[index:]:
                if frame["heading"] is not None:
                    self.headings.append(_text(frame["heading"]))
                if frame["title"] is not None:
                    self.page_title = _text(frame["title"])
                if frame["fragment"] is not None:
                    self.fragments.append(_text(frame["fragment"]))
            del self.frames[index:]
        if tag == "script" and self.script is not None:
            value = "".join(self.script["parts"])
            if len(value.encode("utf-8")) <= MAX_STATE_BYTES:
                if self.script["kind"] == "application/ld+json":
                    self.scripts.append(value)
                elif self.script["kind"] == "application/json" or self.script["id"] in {
                    "__NEXT_DATA__",
                    "__NUXT_DATA__",
                }:
                    self.states.append(value)
                elif re.match(
                    r"\s*(?:(?:window\.)?__(?:INITIAL_STATE|PRELOADED_STATE|APOLLO_STATE)__\s*=)",
                    value,
                ):
                    self.states.append(value.partition("=")[2].strip().rstrip(";"))
            self.script = None
        if tag in BLOCK_TAGS and not any(frame["ignored"] for frame in self.frames):
            self._append("\n")

    def _append(self, data):
        self.parts.append(data)
        if any(frame["main"] for frame in self.frames):
            self.main_parts.append(data)
        for frame in self.frames:
            if frame["heading"] is not None:
                frame["heading"].append(data)
            if frame["fragment"] is not None:
                frame["fragment"].append(data)

    def handle_data(self, data):
        if self.script is not None:
            self.script["parts"].append(data)
        else:
            for frame in self.frames:
                if frame["title"] is not None:
                    frame["title"].append(data)
            if not any(frame["ignored"] for frame in self.frames):
                self._append(data)


def plain_html(value):
    parser = TextParser()
    parser.feed(value)
    return _text(parser.parts)


def portal_name(url):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in GOOGLE_DOMAINS or host in {"g.co", "consent.google.com"}:
        return "Google Jobs"
    if re.fullmatch(r"(?:[a-z]+\.)?indeed\.(?:com|[a-z]{2,3}|co\.[a-z]{2})", host):
        return "Indeed"
    if re.fullmatch(r"(?:[a-z]+\.)?stepstone\.(?:[a-z]{2,3}|co\.[a-z]{2})", host):
        return "StepStone"
    if host == "join.com":
        return "JOIN"
    return "Stellenportal"


def _checked_url(url):
    if not isinstance(url, str) or not 1 <= len(url) <= 2000 or re.search(r"[\x00-\x20\x7f]", url):
        raise HTTPException(
            422,
            "Ungültiger Stellenlink. Bitte die vollständige Adresse kopieren / copy the full job URL.",
        )
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("URL boundary")
        parsed.hostname.encode("idna").decode("ascii")
        return parsed
    except (ValueError, UnicodeError):
        raise HTTPException(
            422,
            "Nur öffentliche HTTPS-Stellenlinks ohne Zugangsdaten erlaubt / public HTTPS job links only.",
        ) from None


def normalize_job_url(url):
    for _ in range(4):
        parsed = _checked_url(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if portal_name(url) == "Indeed" and parsed.path.rstrip("/") in {"", "/jobs"}:
            selected = set(parse_qs(parsed.query).get("vjk", []))
            if len(selected) == 1 and re.fullmatch(r"[a-fA-F0-9]{16}", next(iter(selected))):
                return urlunparse(
                    parsed._replace(
                        path="/viewjob", query=urlencode({"jk": next(iter(selected))}), fragment=""
                    )
                )
        if host not in GOOGLE_DOMAINS:
            return url
        if parsed.path.rstrip("/") == "/url":
            params = parse_qs(parsed.query)
            targets = list(
                dict.fromkeys(
                    value
                    for key in ("url", "q")
                    for value in params.get(key, [])
                    if value.startswith("https://")
                )
            )
            if len(targets) == 1:
                url = targets[0]
                continue
        if parsed.path in {"", "/", "/search", "/url", "/webhp"}:
            raise HTTPException(
                422,
                "Google zeigt eine Jobsuche statt einer direkt lesbaren Stellenanzeige. Öffne den gewünschten Job und kopiere den Link unter „Bewerben auf …“ oder füge den Stellentext unten ein / use the original job posting or paste its text.",
            )
        return url
    raise HTTPException(
        422,
        "Der Google-Link enthält zu viele verschachtelte Weiterleitungen. Bitte den direkten Stellenlink verwenden / use the direct job link.",
    )


def public_address(url):
    parsed = _checked_url(url)
    host = parsed.hostname.encode("idna").decode("ascii")
    try:
        addresses = [item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
    except OSError:
        raise HTTPException(
            422,
            "Stellenlink nicht erreichbar. Bitte Text einfügen / paste the job text instead.",
        ) from None
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise HTTPException(
            422, "Private/interne Adressen nicht erlaubt / private addresses forbidden."
        )
    return (
        host,
        addresses[0],
        quote(parsed.path or "/", safe="/%:@&=+$,;~*'()!-")
        + ("?" + quote(parsed.query, safe="%?&=/:@+$,;~*'()!-") if parsed.query else ""),
    )


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        # macOS Python installations may have no usable system CA bundle. Add
        # Mozilla's roots while retaining configured system/private trust roots.
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        super().__init__(host, timeout=timeout, context=context)
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def fetch_page(url):
    deadline = time.monotonic() + 15
    for _ in range(4):
        url = normalize_job_url(url)
        host, address, path = public_address(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection = PinnedHTTPSConnection(host, address, min(remaining, 8))
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": "TafolliBoostJobImporter/1.1 (+https://tafolliboost.com)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "gzip",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location", "")
                if not location:
                    raise HTTPException(
                        422,
                        "Das Stellenportal liefert eine Weiterleitung ohne Ziel. Bitte den direkten Stellenlink oder Text verwenden / redirect target missing.",
                    )
                url = urljoin(url, location)
                continue
            portal = portal_name(url)
            if response.status in (404, 410):
                raise HTTPException(
                    422,
                    f"{portal}: Die Anzeige ist nicht mehr verfügbar oder der Link ist veraltet. Öffne eine aktuelle Anzeige oder füge ihren Text ein / posting unavailable; use a current job or paste its text.",
                )
            if response.status in (401, 403, 429):
                raise HTTPException(
                    422,
                    f"{portal} lässt den automatischen Abruf gerade nicht zu, etwa wegen Anmeldung oder Zugriffsschutz. Öffne die Anzeige im Browser und kopiere ihre Stellenbeschreibung in das Textfeld / automated access restricted; paste the job text.",
                )
            if response.status != 200:
                raise HTTPException(
                    422,
                    f"{portal} ist gerade nicht erreichbar. Bitte später erneut versuchen oder den Stellentext einfügen / portal unavailable; retry or paste its text.",
                )
            content_type = response.getheader("Content-Type", "").lower()
            encoding = (
                response.getheader("Content-Encoding", "identity").lower().strip() or "identity"
            )
            if "html" not in content_type or encoding not in {"identity", "gzip"}:
                raise HTTPException(
                    422,
                    "Der Link liefert keine lesbare HTML-Stellenanzeige. Bitte die direkte Anzeige öffnen und ihren Text einfügen / use the direct posting or paste its text.",
                )
            parts, size, decoded_size = [], 0, 0
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HTTPException(422, "Import-Zeitüberschreitung / import timed out")
                if connection.sock:
                    connection.sock.settimeout(min(remaining, 8))
                part = response.read1(65536)
                if not part:
                    break
                size += len(part)
                if size > MAX_PAGE_BYTES:
                    raise HTTPException(413, "Webseite zu groß / page too large")
                decoded = (
                    decoder.decompress(part, MAX_PAGE_BYTES - decoded_size + 1) if decoder else part
                )
                decoded_size += len(decoded)
                if decoded_size > MAX_PAGE_BYTES or (decoder and decoder.unconsumed_tail):
                    raise HTTPException(413, "Webseite zu groß / page too large")
                parts.append(decoded)
            if decoder and not decoder.eof:
                raise HTTPException(
                    422,
                    "Das Stellenportal liefert unvollständige Daten. Bitte Text einfügen / incomplete page; paste the job text.",
                )
            data = b"".join(parts)
            charset_match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", content_type)
            charset = charset_match.group(1) if charset_match else "utf-8-sig"
            if charset not in {
                "utf-8",
                "utf-8-sig",
                "utf-16",
                "utf-16-le",
                "utf-16-be",
                "iso-8859-1",
                "windows-1252",
                "cp1252",
                "latin-1",
            }:
                charset = "utf-8-sig"
            return data.decode(charset, errors="replace"), url
        except ssl.SSLCertVerificationError:
            raise HTTPException(
                422,
                "Das HTTPS-Zertifikat der Stellenwebseite konnte nicht geprüft werden. "
                "Bitte die Adresse prüfen oder den Stellentext einfügen / "
                "could not verify the job website's HTTPS certificate.",
            ) from None
        except (OSError, http.client.HTTPException, zlib.error):
            raise HTTPException(
                422,
                "Import fehlgeschlagen. Bitte Stellenbeschreibung kopieren / paste the job text.",
            ) from None
        finally:
            connection.close()
    raise HTTPException(
        422,
        "Zu viele Weiterleitungen oder Zeitüberschreitung / redirect or timeout limit.",
    )


def _walk(value):
    stack = [(value, "", None, 0)]
    for index in range(30000):
        if not stack:
            break
        node, context, parent, depth = stack.pop()
        yield node, context, parent
        if depth >= 60:
            continue
        remaining = 30000 - index - len(stack) - 1
        if remaining <= 0:
            continue
        if isinstance(node, dict):
            stack.extend(
                (item, key, node, depth + 1)
                for key, item in reversed(list(islice(node.items(), remaining)))
            )
        elif isinstance(node, list):
            stack.extend((item, context, parent, depth + 1) for item in reversed(node[:remaining]))


def _is_posting(value):
    kinds = value.get("@type", []) if isinstance(value, dict) else []
    kinds = [kinds] if isinstance(kinds, str) else kinds
    return isinstance(kinds, list) and any(
        isinstance(kind, str) and kind.rstrip("/").rsplit("/", 1)[-1] == "JobPosting"
        for kind in kinds
    )


def find_posting(value):
    return next((node for node, _, _ in _walk(value) if _is_posting(node)), None)


def _string(value):
    return plain_html(value).strip() if isinstance(value, str) else ""


def _company(value):
    for key in ("hiringOrganization", "company", "employer", "companyName", "companyInfoModel"):
        item = value.get(key)
        if isinstance(item, str):
            if not item.lower().startswith(("https://", "http://", "#")):
                return _string(item)[:200]
        if isinstance(item, dict):
            name = item.get("name", item.get("companyName", item.get("displayName", "")))
            if isinstance(name, str):
                return _string(name)[:200]
    return ""


def _description(value):
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (_description(item) for item in value[:100])))
    if isinstance(value, dict):
        # Known text/rich-text fields only; no arbitrary JSON values or script execution.
        return "\n".join(
            filter(
                None,
                (
                    _description(value[key])
                    for key in (
                        "__html",
                        "text",
                        "content",
                        "children",
                        "introduction",
                        "tasks",
                        "responsibilities",
                        "requirements",
                        "qualifications",
                        "benefits",
                    )
                    if key in value
                ),
            )
        )
    return ""


def _record(value, context="", parent=None, method="EmbeddedJSON"):
    if not isinstance(value, dict):
        return None
    is_posting = _is_posting(value)
    key = re.sub(r"[-_]", "", context).lower()
    if (
        not is_posting
        and not any(
            name in value for name in ("jobTitle", "jobDescription", "sanitizedJobDescription")
        )
        and key
        not in {
            "job",
            "jobdata",
            "jobdetail",
            "jobdetails",
            "jobposting",
            "jobinfomodel",
            "vacancy",
            "jobadvertisement",
            "position",
            "posting",
        }
    ):
        return None
    title = _string(
        value.get("title", value.get("jobTitle", value.get("name", value.get("position", ""))))
    )[:200]
    body = next(
        (
            _description(value[name])
            for name in (
                "description",
                "jobDescription",
                "sanitizedJobDescription",
                "descriptionHtml",
                "body",
                "content",
            )
            if name in value and _description(value[name])
        ),
        "",
    )
    for field in (
        "responsibilities",
        "tasks",
        "qualifications",
        "requirements",
        "skills",
        "benefits",
    ):
        extra = _description(value.get(field))
        if extra and extra not in body:
            body += "\n\n" + field + "\n" + extra
    if len(body.strip()) < 30 or (not title and not is_posting):
        return None
    return {
        "title": title,
        "company": _company(value) or (_company(parent) if isinstance(parent, dict) else ""),
        "description": body.strip(),
        "source_url": value.get("url", value.get("mainEntityOfPage", "")),
        "method": "JobPosting" if is_posting else method,
    }


def _url_identity(url, base):
    if isinstance(url, dict):
        url = url.get("@id", url.get("url", ""))
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = _checked_url(urljoin(base, url))
    except HTTPException:
        return None
    params = [
        (key, values)
        for key, values in parse_qs(parsed.query).items()
        if not key.startswith("utm_")
        and key not in {"gclid", "fbclid", "source", "ref", "tracking"}
    ]
    return (
        parsed.hostname.lower().removeprefix("www."),
        parsed.path.rstrip("/"),
        urlencode(sorted(params), doseq=True),
    )


def _choose(records, url, canonical):
    # A search/listing page must not silently import the first of several jobs.
    targets = {_url_identity(url, url), _url_identity(canonical, url)} - {None}
    matched = [record for record in records if _url_identity(record["source_url"], url) in targets]
    if len(matched) == 1:
        return matched[0]
    unique = list(
        {
            (record["title"], record["company"], record["description"]): record
            for record in records
        }.values()
    )
    return unique[0] if len(unique) == 1 else None


def _page_record(parser, url):
    for scripts in (parser.scripts, parser.states):
        records = []
        for script in scripts:
            try:
                value = json.loads(script)
                references = {
                    node["@id"]: node["name"]
                    for node, _, _ in _walk(value)
                    if isinstance(node, dict)
                    and isinstance(node.get("@id"), str)
                    and isinstance(node.get("name"), str)
                }
                for node, context, parent in _walk(value):
                    record = _record(node, context, parent)
                    if record:
                        employer = node.get("hiringOrganization")
                        reference = employer.get("@id") if isinstance(employer, dict) else employer
                        if (
                            not record["company"]
                            and isinstance(reference, str)
                            and reference in references
                        ):
                            record["company"] = _string(references[reference])[:200]
                        records.append(record)
            except (ValueError, RecursionError):
                continue
        selected = _choose(records, url, parser.canonical)
        if selected:
            selected["title"] = selected["title"] or (
                parser.headings[0][:200] if parser.headings else ""
            )
            return selected
        if len(records) > 1:
            raise HTTPException(
                422,
                "Der Link enthält mehrere Stellen. Öffne die gewünschte einzelne Anzeige und kopiere deren Link / select one job posting, not search results.",
            )
    text = (
        "\n\n".join(filter(None, parser.fragments))
        or _text(parser.main_parts)
        or _text(parser.parts)
    )
    title = parser.headings[0][:200] if parser.headings else ""
    if len(text) >= 30 and title:
        return {
            "description": text,
            "title": title,
            "company": "",
            "method": "HTML-JobSection" if parser.fragments else "HTML",
        }
    return None


def _reject_listing_url(url):
    parsed = urlparse(url)
    portal = portal_name(url)
    if (
        (
            portal == "Indeed"
            and (parsed.path.rstrip("/") in {"", "/jobs"} or parsed.path.startswith("/q-"))
        )
        or (portal == "StepStone" and (parsed.path == "/jobs" or parsed.path.startswith("/jobs/")))
        or (portal == "JOIN" and re.fullmatch(r"/companies/[^/]+/?", parsed.path))
    ):
        raise HTTPException(
            422,
            f"{portal}: Das ist eine Such- oder Firmenseite. Kopiere den Link zur einzelnen Stellenanzeige / use a single job posting, not a search or company page.",
        )


def _reject_non_job_page(parser, url):
    parsed = urlparse(url)
    portal = portal_name(url)
    headings = " ".join([parser.page_title, *parser.headings]).lower()
    if re.search(
        r"just a moment|authenticating|access denied|attention required|verify (?:that )?you(?: are|'re) human|robot check|zugriff verweigert|bestätigen.{0,25}(?:mensch|kein roboter)",
        headings,
    ):
        raise HTTPException(
            422,
            f"{portal} zeigt eine Zugriffskontrolle statt der Stellenanzeige. Öffne die Anzeige im Browser und füge ihren Text unten ein / verification page; paste the job text.",
        )
    if parsed.hostname == "consent.google.com" or re.search(
        r"before you continue to google|bevor sie zu google", headings
    ):
        raise HTTPException(
            422,
            "Google zeigt eine Einwilligungsseite. Bitte den Original-Link unter „Bewerben auf …“ oder den Stellentext verwenden / use the original posting, not Google consent.",
        )
    if re.search(
        r"(?:job|posting|position).{0,30}(?:no longer available|has expired)|(?:stelle|anzeige).{0,30}(?:nicht mehr verfügbar|abgelaufen)",
        headings,
    ):
        raise HTTPException(
            422,
            f"{portal}: Die Stellenanzeige ist abgelaufen. Bitte eine aktuelle Anzeige oder ihren Text verwenden / expired posting.",
        )
    _reject_listing_url(url)


def import_job(url):
    original = url
    url = normalize_job_url(url)
    visited = set()
    for attempt in range(2):
        _reject_listing_url(url)
        html, final_url = fetch_page(url)
        visited.update((url, final_url))
        parser = TextParser()
        try:
            parser.feed(html)
            _reject_non_job_page(parser, final_url)
            record = _page_record(parser, final_url)
        except (ValueError, RecursionError):
            record = None
        if record:
            text = record["description"]
            email = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I)
            return {
                "url": urlunparse(urlparse(final_url)._replace(fragment="")),
                "description": text[:20000],
                "title": record["title"],
                "company": record["company"],
                "email": email.group() if email else "",
                "method": record["method"],
                "provider": portal_name(final_url),
                "resolved_from": original if final_url != original else "",
                "needs_review": True,
                "truncated": len(text) > 20000,
            }
        target = urljoin(final_url, parser.canonical) if parser.canonical else ""
        if attempt == 0 and target and target not in visited:
            # One canonical hop, through the same DNS-pinned transport and HTTPS checks.
            url = normalize_job_url(target)
            continue
        break
    raise HTTPException(
        422,
        "Kein vollständiger Stellentext im öffentlich abrufbaren Inhalt gefunden. Die Anzeige kann JavaScript oder Anmeldung benötigen. Öffne sie im Browser und füge die Stellenbeschreibung unten ein / paste the complete job description.",
    )
