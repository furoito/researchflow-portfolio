"""Extract grounded fields from uploaded HTML. Never fetch arbitrary URLs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from bs4 import BeautifulSoup

MAX_HTML_CHARS = 300_000
MAX_BODY_CHARS = 3_000


@dataclass(frozen=True)
class ExtractedPage:
    source_id: str
    title: str
    description: str
    heading: str
    body: str
    location: str
    event_date: str
    source_url: str
    source_type: str  # demo-html / uploaded-html

    @property
    def model_input(self) -> str:
        return " ".join(filter(None, [self.title, self.description, self.heading, self.body[:1200]]))


def _clean(value: Any, *, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized[:limit]


def _meta(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str:
    attrs = {"name": name} if name else {"property": prop}
    node = soup.find("meta", attrs=attrs)
    return _clean(node.get("content", "") if node else "", limit=450)


def _iter_json_nodes(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _iter_json_nodes(item)
    elif isinstance(value, dict):
        yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            nested = value.get(key)
            if nested is not None:
                yield from _iter_json_nodes(nested)


def _jsonld(soup: BeautifulSoup) -> list[dict]:
    nodes: list[dict] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "")[:40_000]
        if not raw:
            continue
        try:
            nodes.extend(_iter_json_nodes(json.loads(raw)))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return nodes


def _json_address(value: Any) -> str:
    if isinstance(value, str):
        return _clean(value, limit=120)
    if not isinstance(value, dict):
        return ""
    pieces = [value.get(k, "") for k in ("addressRegion", "addressLocality", "streetAddress")]
    return _clean(" ".join(piece for piece in pieces if isinstance(piece, str)), limit=120)


def _structured_fields(nodes: list[dict]) -> tuple[str, str, str]:
    structured_title = ""
    location = ""
    date = ""
    for node in nodes:
        if not structured_title:
            structured_title = _clean(node.get("headline") or node.get("name") or "")
        if not location:
            addr = node.get("address")
            if not addr and isinstance(node.get("location"), dict):
                addr = node["location"].get("address")
            location = _json_address(addr)
        if not date:
            node_type = node.get("@type", "")
            is_event = node_type == "Event" or (isinstance(node_type, list) and "Event" in node_type)
            if is_event:
                date = _clean(node.get("startDate", ""), limit=60)
    return structured_title, location, date


def extract_page(html: str, *, source_id: str, source_url: str = "", source_type: str = "demo-html") -> ExtractedPage:
    if not isinstance(html, str) or not html.strip():
        raise ValueError("HTMLが空です。")
    if len(html) > MAX_HTML_CHARS:
        raise ValueError("HTMLが大きすぎます。最大300,000文字です。")

    soup = BeautifulSoup(html, "html.parser")
    nodes = _jsonld(soup)
    structured_title, location, event_date = _structured_fields(nodes)
    title_tag = soup.find("title")
    title = (_meta(soup, prop="og:title") or
             _clean(title_tag.get_text(" ", strip=True) if title_tag else "") or structured_title)
    description = (_meta(soup, name="description") or _meta(soup, prop="og:description"))
    heading_tag = soup.find("h1")
    heading = _clean(heading_tag.get_text(" ", strip=True) if heading_tag else "")

    # Remove decorative sections and executable/script contents before extracting prose.
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
        tag.decompose()
    content = soup.find("main") or soup.find("article") or soup.body or soup
    body = _clean(content.get_text(" ", strip=True), limit=MAX_BODY_CHARS)
    if not (title or description or heading or body):
        raise ValueError("ページ本文から文字情報を抽出できませんでした。")
    return ExtractedPage(
        source_id=source_id,
        title=title or heading or "（タイトルなし）",
        description=description,
        heading=heading,
        body=body,
        location=location,
        event_date=event_date,
        source_url=_clean(source_url, limit=450),
        source_type=source_type,
    )


def extracted_summary(page: ExtractedPage, max_chars: int = 100) -> str:
    """Deterministic extractive overview, NOT a generative AI summary."""
    base = page.description or page.body
    cleaned = _clean(base, limit=max_chars + 10)
    if not cleaned:
        return "（概要なし）"
    return cleaned[:max_chars] + ("…" if len(cleaned) > max_chars else "")
