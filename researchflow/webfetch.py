"""Bounded public-URL retrieval for a human-triggered portfolio workflow.

No JavaScript, no crawling, no proxies, no direct IP URLs. DNS answers are
validated and the TCP socket is pinned to the validated address to guard
against DNS rebinding. This is not intended as a general-purpose crawler.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
import zlib

MAX_URLS = 8
MAX_BYTES = 4_000_000
MAX_ROBOTS_BYTES = 100_000
TIMEOUT_SECONDS = 7
USER_AGENT = "ResearchFlowPortfolio/0.6 (manual research; no crawler)"
MAX_REDIRECTS = 3

class FetchError(ValueError):
    """A safe-to-display, expected error from URL retrieval."""

@dataclass(frozen=True)
class FetchedPage:
    url: str
    html: str
    status: int
    partial: bool = False


def validate_public_url(value: str) -> str:
    """Syntactically validate a direct URL before any DNS request."""
    value = value.strip()
    if not value or len(value) > 1800 or any(ord(c) < 33 for c in value):
        raise FetchError("URL format is invalid or too long")
    if '\\' in value:
        raise FetchError("Backslashes are not supported in URLs")
    try:
        p = urlsplit(value)
        host = (p.hostname or "").rstrip('.').lower().encode('idna').decode('ascii')
        port = p.port
    except (ValueError, UnicodeError) as exc:
        raise FetchError("URL host or port is invalid") from exc
    if p.scheme not in ('http', 'https') or not host or p.username or p.password:
        raise FetchError("Only public HTTP/HTTPS URLs without credentials are supported")
    if host == 'localhost' or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid')):
        raise FetchError("Local or test hosts are not accessible")
    if ':' in host or re.fullmatch(r'[0-9.]+', host):
        raise FetchError("Direct IP-address URLs are not supported")
    if '.' not in host or any(len(label) > 63 or not re.fullmatch(r'[a-z0-9-]+', label) or label.startswith('-') or label.endswith('-') for label in host.split('.')):
        raise FetchError("Hostname is not a valid public DNS name")
    if port not in (None, 80 if p.scheme == 'http' else 443):
        raise FetchError("Nonstandard ports are not supported")
    if not p.netloc or len(host) > 253:
        raise FetchError("Hostname is invalid")
    netloc = host
    # Fragments are client-only and not part of the fetched resource.
    return urlunsplit((p.scheme, netloc, p.path or '/', p.query, ''))


def resolve_public_ip(host: str, port: int) -> str:
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError("Host could not be resolved") from exc
    if not answers:
        raise FetchError("Host has no DNS records")
    ips = list(dict.fromkeys(answer[4][0] for answer in answers))
    for ip in ips:
        try:
            parsed_ip = ipaddress.ip_address(ip)
        except ValueError as exc:
            raise FetchError("Host returned an invalid network address") from exc
        if not parsed_ip.is_global:
            raise FetchError("Host resolves to a private or reserved network")
    # An IP address is pinned for the lifetime of this HTTP connection.
    return next((ip for ip in ips if ':' not in ip), ips[0])


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, *, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), timeout=self.timeout)


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, *, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        raw = socket.create_connection((self._ip, self.port), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def _request_once(url: str, *, max_bytes: int = MAX_BYTES) -> tuple[int, dict[str, str], bytes]:
    parsed = urlsplit(validate_public_url(url))
    host = parsed.hostname
    assert host is not None
    port = 443 if parsed.scheme == 'https' else 80
    ip = resolve_public_ip(host, port)
    klass = _HTTPSConnection if parsed.scheme == 'https' else _HTTPConnection
    conn = klass(host, port, ip=ip)
    try:
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        conn.request('GET', path, headers={
            'Host': host, 'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.5',
            'Accept-Encoding': 'identity', 'Connection': 'close',
        })
        response = conn.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        headers.pop("x-researchflow-partial", None)  # Internal marker must not come from the website.
        try:
            reported_length = int(headers.get('content-length', '0') or 0)
        except ValueError as exc:
            raise FetchError("Invalid HTTP content length") from exc
        # Redirect responses do not need a body; the destination is checked
        # separately, including its DNS address and robots rules.
        if response.status in (301, 302, 303, 307, 308):
            return response.status, headers, b""

        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        partial_ok = (
            max_bytes == MAX_BYTES
            and response.status == 200
            and content_type in ("text/html", "application/xhtml+xml")
        )
        # Keep robots.txt strict: never attempt to decide permission based on a
        # partial robots file. Page HTML, however, can often be meaningfully
        # extracted from its beginning even if the tail is enormous.
        if reported_length > max_bytes and not partial_ok:
            raise FetchError("Response is too large")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes or reported_length > max_bytes:
            if not partial_ok:
                raise FetchError("Response exceeds the size limit")
            body = body[:max_bytes]
            # Internal marker, not a user-supplied HTTP header.
            headers["x-researchflow-partial"] = "1"
        return response.status, headers, body
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as exc:
        raise FetchError("Connection failed, was blocked, or timed out") from exc
    finally:
        conn.close()


def _decode(body: bytes, headers: dict[str, str], max_bytes: int) -> str:
    encoding = headers.get('content-encoding', '').lower().strip()
    if encoding == 'gzip':
        try:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            body = d.decompress(body, max_bytes + 1)
            if len(body) > max_bytes or d.unconsumed_tail:
                raise FetchError("Expanded response is too large")
            body += d.flush(max_bytes + 1 - len(body))
        except zlib.error as exc:
            raise FetchError("Invalid compressed response") from exc
    elif encoding not in ('', 'identity'):
        raise FetchError("Unsupported HTTP content encoding")
    if len(body) > max_bytes:
        raise FetchError("Expanded response is too large")
    content_type = headers.get('content-type', '')
    m = re.search(r'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', content_type)
    codec = m.group(1) if m else 'utf-8'
    try:
        return body.decode(codec)
    except (LookupError, UnicodeDecodeError):
        if headers.get("x-researchflow-partial") == "1":
            # A bounded response may end mid-codepoint. Do not interpret the
            # entire UTF-8 page as CP932 just because of the final byte.
            try:
                return body.decode(codec, errors='replace')
            except LookupError:
                return body.decode('utf-8', errors='replace')
        try:
            # Common fallback for Japanese news and tourism sites.
            return body.decode('cp932')
        except UnicodeDecodeError:
            return body.decode('utf-8', errors='replace')


def _follow(url: str, *, max_bytes: int, is_robots: bool = False) -> tuple[int, dict[str, str], bytes, str]:
    current = validate_public_url(url)
    seen: set[str] = set()
    for _ in range(MAX_REDIRECTS + 1):
        if current in seen:
            raise FetchError("Redirect loop detected")
        seen.add(current)
        status, headers, body = _request_once(current, max_bytes=max_bytes)
        if status in (301, 302, 303, 307, 308):
            target = headers.get('location', '')
            if not target:
                raise FetchError("Redirect has no destination")
            next_url = validate_public_url(urljoin(current, target))
            if urlsplit(current).scheme == 'https' and urlsplit(next_url).scheme != 'https':
                raise FetchError("HTTPS to HTTP redirect is blocked")
            if not is_robots:
                _check_robots(next_url)
            current = next_url
            continue
        return status, headers, body, current
    raise FetchError("Too many redirects")


def _check_robots(url: str) -> None:
    p = urlsplit(url)
    origin = f'{p.scheme}://{p.netloc}'
    robots_url = origin + '/robots.txt'
    try:
        status, headers, data, _ = _follow(robots_url, max_bytes=MAX_ROBOTS_BYTES, is_robots=True)
        if status in (404, 410):
            allowed = True
        elif status != 200:
            raise FetchError("Cannot confirm robots.txt permission")
        else:
            rules = _decode(data, headers, MAX_ROBOTS_BYTES)
            parser = RobotFileParser()
            parser.parse(rules.splitlines())
            allowed = parser.can_fetch(USER_AGENT, url)
            delay = parser.crawl_delay(USER_AGENT)
            if delay is not None and delay > 0:
                raise FetchError("Website asks for a crawl delay; please use HTML upload")
        if not allowed:
            raise FetchError("Access not permitted by robots.txt")
    except FetchError as exc:
        raise FetchError(str(exc)) from exc


def _compact_web_html(html: str) -> tuple[str, bool]:
    """Drop bulky embedded code before parsing; bound parser input.

    This is only applied to fetched web pages. Large downloadable documents
    remain unsupported, and the original page is not represented as complete
    when actual HTML content must be truncated.
    """
    from .extract import MAX_HTML_CHARS

    if len(html) <= MAX_HTML_CHARS:
        return html, False
    # Ordinary scripts, style sheets and inline SVG frequently account for the
    # majority of modern page HTML. JSON-LD may contain location/event facts,
    # so retain small valid structured-data blocks for extract_page().
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    def keep_structured_data(match: re.Match[str]) -> str:
        script = match.group(0)
        tag = script[:script.find('>') + 1]
        ldjson = re.search(r"\btype\s*=\s*(?:[\"']application/ld\+json[\"']|application/ld\+json(?:\s|>))", tag, flags=re.I)
        return script if ldjson and len(script) <= 40_000 else ""

    html = re.sub(r"<script\b[^>]*>.*?</script\s*>", keep_structured_data, html, flags=re.I | re.S)
    html = re.sub(r"<(?:style|svg)\b[^>]*>.*?</(?:style|svg)\s*>", "", html, flags=re.I | re.S)
    is_cut = len(html) > MAX_HTML_CHARS
    return html[:MAX_HTML_CHARS] if is_cut else html, is_cut


def fetch_public_page(url: str) -> FetchedPage:
    url = validate_public_url(url)
    _check_robots(url)
    status, headers, body, final_url = _follow(url, max_bytes=MAX_BYTES)
    if status != 200:
        raise FetchError(f"Website returned HTTP {status}")
    ctype = headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if ctype not in ('text/html', 'application/xhtml+xml'):
        raise FetchError("URL did not return an HTML page")
    text = _decode(body, headers, MAX_BYTES)
    text, parser_cut = _compact_web_html(text)
    if not text.strip():
        raise FetchError("Response contains no readable HTML")
    return FetchedPage(
        url=final_url, html=text, status=status,
        partial=(headers.get("x-researchflow-partial") == "1" or parser_cut),
    )


def parse_url_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > MAX_URLS:
        raise FetchError(f"No more than {MAX_URLS} URLs per batch")
    return lines


def gather_web_sources(urls: list[str], *, fetcher=fetch_public_page) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Fetch each user-requested URL; return source tuples + per-item errors."""
    if len(urls) > MAX_URLS:
        raise FetchError(f"No more than {MAX_URLS} URLs per batch")
    sources: list[tuple[str, str, str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(urls, 1):
        try:
            normalized = validate_public_url(value)
            if normalized in seen:
                errors.append(f"URL {index}: duplicate input")
                continue
            seen.add(normalized)
            page = fetcher(normalized)
            if page.url in seen and page.url != normalized:
                errors.append(f"URL {index}: duplicate redirect target")
                continue
            seen.add(page.url)
            sources.append((f'URL {index}', page.html, page.url, 'web-url-partial' if page.partial else 'web-url'))
        except (FetchError, ValueError) as exc:
            errors.append(f'URL {index}: {exc}')
    return sources, errors
