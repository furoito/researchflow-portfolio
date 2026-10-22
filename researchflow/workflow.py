"""Review workflow: user amendments are explicit and exported, never fabricated."""
from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from .classify import CATEGORIES
from .process import ResearchRecord

REVIEW_STATES = ("要確認", "確認済み", "保留", "対象外")
EDITABLE = ("ページタイトル", "カテゴリ", "概要", "所在地", "開催日", "確認状況", "確認メモ")


def apply_review(records: Sequence[ResearchRecord], rows: Sequence[Mapping[str, object]]) -> list[ResearchRecord]:
    """Apply strictly constrained, row-preserving edits from the table UI."""
    if len(records) != len(rows):
        raise ValueError("編集前後のレコード件数が一致しません。")
    updated = []
    for original, row in zip(records, rows):
        fields = {name: str(row.get(name) or "").strip() for name in EDITABLE}
        if fields["カテゴリ"] not in CATEGORIES:
            raise ValueError("カテゴリの選択値が不正です。")
        if fields["確認状況"] not in REVIEW_STATES and fields["確認状況"] != "要確認（デモ）":
            raise ValueError("確認状況の選択値が不正です。")
        if any(len(text) > 1500 for text in fields.values()):
            raise ValueError("入力内容が長すぎます。")
        updated.append(replace(
            original,
            title=fields["ページタイトル"],
            category=fields["カテゴリ"],
            summary=fields["概要"],
            location=fields["所在地"].replace("未記載", "") if fields["所在地"] == "未記載" else fields["所在地"],
            event_date="" if fields["開催日"] == "未記載" else fields["開催日"],
            review_status=fields["確認状況"],
            review_note=fields["確認メモ"],
        ))
    return updated
