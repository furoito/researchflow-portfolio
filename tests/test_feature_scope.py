"""Unfinished fields must not appear on public product surfaces."""
import csv
from dataclasses import fields
from io import StringIO
from pathlib import Path
from researchflow.extract import ExtractedPage
from researchflow.process import EXPORT_COLUMNS, ResearchRecord, process_sources, to_csv_bytes
from researchflow.workflow import EDITABLE
ROOT = Path(__file__).resolve().parents[1]
def test_no_unfinished_data_fields_in_public_schema(samples):
    assert "所在地" not in EXPORT_COLUMNS and "開催日" not in EXPORT_COLUMNS
    assert "所在地" not in EDITABLE and "開催日" not in EDITABLE
    assert "location" not in [f.name for f in fields(ResearchRecord)]
    assert "event_date" not in [f.name for f in fields(ExtractedPage)]
    rows, errors = process_sources([(s["id"], text, s["url"], "demo-html") for s, text in samples])
    assert not errors and len(rows) == 6
    output = next(csv.DictReader(StringIO(to_csv_bytes(rows).decode("utf-8-sig"))))
    assert set(output) == set(EXPORT_COLUMNS)
    assert "分類根拠" in output and "カテゴリ" in output

def test_unfinished_features_are_not_advertised():
    for filename in ["README.md", "researchflow/presentation.py", "templates/preview_template.html", "scripts/offline_preview.js", "preview.html"]:
        txt = (ROOT / filename).read_text(encoding="utf-8")
        assert "所在地" not in txt and "開催日" not in txt, filename
    assert "カテゴリ・概要・確認状況を編集できます" in (ROOT / "app.py").read_text(encoding="utf-8")
