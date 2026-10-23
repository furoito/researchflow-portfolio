"""Generate a styled, offline preview using real local processing results.

This static page is not evidence that Streamlit itself was started.
"""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from researchflow.presentation import DEMO_INTRO, FEATURE, FOOTER, HERO, SITE_HEADER, WORKFLOW
from researchflow.process import process_sources, to_csv_bytes
from researchflow.classify import CATEGORIES


def build() -> None:
    samples = json.loads((ROOT / "samples" / "index.json").read_text(encoding="utf-8"))
    source_items = [
        (sample["id"], (ROOT / "samples" / sample["file"]).read_text(encoding="utf-8"), sample["url"], "demo-html")
        for sample in samples
    ]
    records, errors = process_sources(source_items)
    if errors or len(records) != len(samples):
        raise RuntimeError(f"Unexpected demo output: {errors}; rows: {len(records)}")

    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    rows = "\n".join(
        '<tr data-category="' + esc(record.category) + '" data-source-url="' + esc(record.url) + '">' +
        '<td><div class="rf-row-title">' + esc(record.title) + '</div><div class="rf-row-url">' + esc(record.url) + '</div></td>' +
        '<td><select class="rf-category-edit" aria-label="カテゴリを編集">' + ''.join('<option value="' + esc(category) + '"' + (' selected' if category == record.category else '') + '>' + esc(category) + '</option>' for category in CATEGORIES) + '</select></td>' +
        '<td>' + esc(record.summary) + '</td>' +
        '<td>' + esc(record.location or "記載なし") + '</td>' +
        '<td>' + esc(record.event_date or "—") + '</td>' + '<td><select class="rf-status-edit" aria-label="確認状況を編集"><option>要確認</option><option>確認済み</option><option>保留</option><option>対象外</option></select></td></tr>'
        for record in records
    )
    template = (ROOT / "templates" / "preview_template.html").read_text(encoding="utf-8")
    replacements = {
        "<!--RF_CSS-->": (ROOT / "assets" / "editorial.css").read_text(encoding="utf-8"),
        "<!--RF_HEADER-->": SITE_HEADER,
        "<!--RF_HERO-->": HERO,
        "<!--RF_FEATURE-->": FEATURE,
        "<!--RF_WORKFLOW-->": WORKFLOW,
        "<!--RF_DEMO_INTRO-->": DEMO_INTRO,
        "<!--RF_FOOTER-->": FOOTER,
        "<!--RF_COUNT-->": str(len(records)),
        "<!--RF_CATEGORIES-->": str(len({record.category for record in records})),
        "<!--RF_ERRORS-->": str(len(errors)),
        "<!--RF_ROWS-->": rows,
        "<!--RF_CSV-->": base64.b64encode(to_csv_bytes(records)).decode("ascii"),
    }
    for placeholder, value in replacements.items():
        if template.count(placeholder) != 1:
            raise ValueError(f"Expected exactly one {placeholder} placeholder")
        template = template.replace(placeholder, value)
    (ROOT / "preview.html").write_text(template, encoding="utf-8")
    (ROOT / "assets" / "sample_results.csv").write_bytes(to_csv_bytes(records))
    print(f"Generated preview.html from {len(records)} processed samples")


if __name__ == "__main__":
    build()
