"""Bounded public HTTPS importer with DNS pinning and redirect validation."""

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import certifi
from fastapi import HTTPException


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.scripts, self.script, self.ignore = [], [], None, 0
        self.headings, self.heading = [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "nav", "footer", "header"):
            self.ignore += 1
        if tag == "h1" and not self.ignore:
            self.heading = []
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.script = ""
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3") and not self.ignore:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "h1" and self.heading is not None:
            self.headings.append("".join(self.heading).strip())
            self.heading = None
        if tag == "script" and self.script is not None:
            self.scripts.append(self.script)
            self.script = None
        if tag in ("script", "style", "nav", "footer", "header"):
            self.ignore = max(0, self.ignore - 1)

    def handle_data(self, data):
        if self.script is not None:
            self.script += data
        elif not self.ignore:
            self.parts.append(data)
            if self.heading is not None:
                self.heading.append(data)


def plain_html(value):
    parser = TextParser()
    parser.feed(value)
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def public_address(url):
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Ungültiger Stellenlink / invalid URL") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in (None, 443)
    ):
        raise HTTPException(
            422,
            "Nur öffentliche HTTPS-Stellenlinks erlaubt / public HTTPS job links only.",
        )
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
        (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
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
                    "User-Agent": "ApplicationJobImporter/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader("Location", ""))
                continue
            if (
                response.status != 200
                or "html" not in response.getheader("Content-Type", "")
                or response.getheader("Content-Encoding", "identity") != "identity"
            ):
                raise HTTPException(
                    422,
                    "Stellenportal blockiert Import oder benötigt Anmeldung. Bitte Text einfügen / portal blocks import; paste the text.",
                )
            parts, size = [], 0
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
                if size > 2 * 1024 * 1024:
                    raise HTTPException(413, "Webseite zu groß / page too large")
                parts.append(part)
            data = b"".join(parts)
            if len(data) > 2 * 1024 * 1024:
                raise HTTPException(413, "Webseite zu groß / page too large")
            return data.decode("utf-8", errors="replace"), url
        except ssl.SSLCertVerificationError:
            raise HTTPException(
                422,
                "Das HTTPS-Zertifikat der Stellenwebseite konnte nicht geprüft werden. "
                "Bitte die Adresse prüfen oder den Stellentext einfügen / "
                "could not verify the job website's HTTPS certificate.",
            ) from None
        except (OSError, http.client.HTTPException):
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


def find_posting(value):
    if isinstance(value, dict):
        if "JobPosting" in (
            [value.get("@type")] if isinstance(value.get("@type"), str) else value.get("@type", [])
        ):
            return value
        for item in value.values():
            found = find_posting(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_posting(item)
            if found:
                return found
    return None


def import_job(url):
    html, final_url = fetch_page(url)
    parser = TextParser()
    parser.feed(html)
    posting = None
    for script in parser.scripts:
        try:
            posting = find_posting(json.loads(script))
        except (ValueError, RecursionError):
            continue
        if posting:
            break
    if posting:
        employer = posting.get("hiringOrganization", {})
        text = plain_html(str(posting.get("description", "")))
        title = str(posting.get("title", ""))[:200]
        company = str(employer.get("name", ""))[:200] if isinstance(employer, dict) else ""
    else:
        text = plain_html(html)
        title = parser.headings[0][:200] if parser.headings else ""
        company = ""
    if len(text) < 30:
        raise HTTPException(
            422,
            "Kein lesbarer Stellentext. Bitte Text einfügen / paste the job description.",
        )
    return {
        "url": final_url,
        "description": text[:20000],
        "title": title,
        "company": company,
        "email": (
            re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I).group()
            if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I)
            else ""
        ),
        "method": "JobPosting" if posting else "HTML",
        "needs_review": True,
        "truncated": len(text) > 20000,
    }
