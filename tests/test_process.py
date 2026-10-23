import csv
from io import BytesIO, StringIO

from researchflow.process import ResearchRecord, process_sources, to_csv_bytes


def test_complete_sample_pipeline(samples):
    rows = [(meta["id"], html, meta["url"], "demo-html") for meta, html in samples]
    records, errors = process_sources(rows)
    assert len(records) == 6
    assert errors == []
    assert [r.category for r in records].count("イベント") == 2
    assert all(r.review_status == "要確認（デモ）" for r in records)
    assert all(r.categorization_method in ("明示語句による分類", "ローカル軽量ML（暫定）", "分類保留", "URL構造による分類") for r in records)
    assert all(r.classification_reason for r in records)
    csv_bytes = to_csv_bytes(records)
    assert csv_bytes[:3] == b"\xef\xbb\xbf"
    content = csv_bytes.decode("utf-8-sig")
    parsed = list(csv.DictReader(StringIO(content)))
    assert len(parsed) == 6
    assert parsed[0]["ページタイトル"] == records[0].title


def test_duplicate_url_is_skipped(samples):
    meta, html = samples[0]
    rows = [("first", html, meta["url"], "demo-html"), ("second", html, meta["url"], "demo-html")]
    records, errors = process_sources(rows)
    assert len(records) == 1
    assert "重複" in errors[0]


def test_csv_formula_injection_is_escaped():
    row = ResearchRecord(
        title='=HYPERLINK("https://fake.invalid")', category="その他", summary="@SUM(A1:A4)",
        url="=cmd", extraction_method="html", categorization_method="ml", review_status="未確認",
    )
    content = to_csv_bytes([row]).decode("utf-8-sig")
    data = list(csv.DictReader(StringIO(content)))[0]
    assert data["ページタイトル"].startswith("'=")
    assert data["概要"].startswith("'@")
    assert data["参照URL"].startswith("'=")


def test_invalid_html_is_reported_and_other_entries_continue(samples):
    meta, html = samples[0]
    records, errors = process_sources([("broken", " ", "", "uploaded-html"), (meta["id"], html, meta["url"], "demo-html")])
    assert len(records) == 1
    assert len(errors) == 1
