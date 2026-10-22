"""End-to-end pipeline, including evidence provenance and safe CSV export."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from io import StringIO
import re

from .classify import classify_local
from .extract import ExtractedPage, extract_page, extracted_summary
from .gemini import enrich_with_gemini

MAX_DOCUMENTS = 8
EXPORT_COLUMNS = ["ページタイトル", "カテゴリ", "概要", "所在地", "開催日", "参照URL", "抽出方法", "分類方法", "確認状況", "確認メモ", "入力元"]


@dataclass(frozen=True)
class ResearchRecord:
    title: str
    category: str
    summary: str
    location: str
    event_date: str
    url: str
    extraction_method: str
    categorization_method: str
    review_status: str
    ml_score: float | None = None
    review_note: str = ""
    source_kind: str = ""
    evidence_excerpt: str = ""

    def display_dict(self) -> dict:
        return {
            "ページタイトル": self.title,
            "カテゴリ": self.category,
            "概要": self.summary,
            "所在地": self.location or "未記載",
            "開催日": self.event_date or "未記載",
            "参照URL": self.url or "（入力なし）",
            "抽出方法": self.extraction_method,
            "分類方法": self.categorization_method,
            "確認状況": self.review_status,
            "確認メモ": self.review_note,
            "入力元": self.source_kind or "未指定",
        }


def make_record(page: ExtractedPage, *, mode: str = "local", api_key: str = "") -> ResearchRecord:
    category, score = classify_local(page.model_input)
    summary = extracted_summary(page)
    method = "ローカル軽量ML（無料）"
    if mode == "gemini":
        category, summary = enrich_with_gemini(page.title, page.model_input, api_key=api_key)
        method = "Gemini 2.5 Flash-Lite（API）"
        score = None
    return ResearchRecord(
        title=page.title,
        category=category,
        summary=summary,
        location=page.location,
        event_date=page.event_date,
        url=page.source_url,
        extraction_method="BeautifulSoup（HTML）",
        categorization_method=method,
        review_status="要確認（デモ）" if page.source_type == "demo-html" else "要確認",
        source_kind={"web-url": "公開URL", "uploaded-html": "HTMLファイル", "demo-html": "サンプル"}.get(page.source_type, page.source_type),
        evidence_excerpt=(page.description or page.heading or page.body)[:230],
        ml_score=score,
    )


def process_sources(sources: list[tuple[str, str, str, str]], *, mode: str = "local", api_key: str = "") -> tuple[list[ResearchRecord], list[str]]:
    """sources: (source_id, html, source_url, source_type)."""
    if len(sources) > MAX_DOCUMENTS:
        raise ValueError(f"一度に処理できるのは最大{MAX_DOCUMENTS}件です。")
    records, errors = [], []
    seen: set[str] = set()
    for source_id, html, source_url, source_type in sources:
        try:
            page = extract_page(html, source_id=source_id, source_url=source_url, source_type=source_type)
            key = re.sub(r"\s+", "", page.source_url.lower()) if page.source_url else page.title.casefold()
            if key in seen:
                errors.append(f"{source_id}: 重複したためスキップしました。")
                continue
            seen.add(key)
            records.append(make_record(page, mode=mode, api_key=api_key))
        except Exception as exc:
            from .gemini import GeminiError
            if isinstance(exc, GeminiError):
                errors.append(f"{source_id}: {exc}")
            elif isinstance(exc, ValueError):
                errors.append(f"{source_id}: {exc}")
            else:
                errors.append(f"{source_id}: 処理に失敗しました（入力形式を確認してください）。")
    return records, errors


def _csv_safe(value: object) -> str:
    text = str(value if value is not None else "")
    # Prevent spreadsheet formula execution on direct CSV opening.
    if re.match(r"^\s*[=+@\-\t\r]", text):
        return "'" + text
    return text


def to_csv_bytes(records: list[ResearchRecord]) -> bytes:
    buf = StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({key: _csv_safe(value) for key, value in record.display_dict().items()})
    return buf.getvalue().encode("utf-8-sig")
