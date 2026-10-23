import csv
from io import StringIO
import pytest
from researchflow.process import ResearchRecord, to_csv_bytes
from researchflow.workflow import apply_review


def record():
    return ResearchRecord('Cafe','グルメ','Description','', '', 'https://example.com/page', 'html','ml','要確認',.44,source_kind='公開URL',evidence_excerpt='Original text')

def test_human_edit_is_used_in_export():
    r = record()
    data = r.display_dict()
    data.update({'カテゴリ':'イベント','概要':'=SUM(1,2)','確認状況':'確認済み','確認メモ':'ソース確認','所在地':'横浜市'})
    reviewed=apply_review([r],[data])[0]
    assert reviewed.url==r.url
    assert reviewed.category=='イベント'
    assert reviewed.classification_reason=='手動修正（自動判定: グルメ）'
    assert reviewed.review_status=='確認済み'
    assert reviewed.evidence_excerpt==r.evidence_excerpt
    row=next(csv.DictReader(StringIO(to_csv_bytes([reviewed]).decode('utf-8-sig'))))
    assert row['概要'].startswith("'=")
    assert row['確認メモ']=='ソース確認'
    assert row['入力元']=='公開URL'

def test_illegal_status_and_changed_count_are_blocked():
    r=record()
    data=r.display_dict()
    data['確認状況']='承認済'
    with pytest.raises(ValueError):apply_review([r],[data])
    with pytest.raises(ValueError):apply_review([r],[])
