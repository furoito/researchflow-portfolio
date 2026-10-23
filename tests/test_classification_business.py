"""Targeted, manually expected page-purpose scenarios.

Cases are separate from the generated training examples; these tests do NOT
constitute an independently sampled accuracy evaluation.
"""
import csv
from dataclasses import replace
from io import StringIO
import pytest

from researchflow.classify import CATEGORIES, TRAINING_SAMPLES, classify_page
from researchflow.process import process_sources, to_csv_bytes
from researchflow.workflow import apply_review


REAL_COMPANY_METADATA = [
    # Actual HTML titles/summaries previously exported from public companies.
    ("会社案内 | 札幌のホームページ制作・Web制作ならアートバイブス", "2003年の創業以来、Web制作を行う有限会社アートバイブスの会社概要", "https://artvibes.co.jp/company/", "企業・団体"),
    ("企業概要 | サイボウズ株式会社", "本社所在地、代表者、従業員数など会社の基本情報", "https://cybozu.co.jp/company/outline/", "企業・団体"),
    ("会社概要 | さくらインターネット", "さくらインターネットの会社概要をご覧いただけます", "https://www.sakura.ad.jp/corporate/corp/profile/", "企業・団体"),
    ("会社概要 - オウンドメディア戦略ラボ by はてな", "オウンドメディアを運営する株式会社はてなの会社情報", "https://www.hatena.ne.jp/ownedmedia/company", "企業・団体"),
    ("札幌のホームページ制作・Web制作ならアートバイブス", "Web制作・企画運営を行う制作会社", "https://artvibes.co.jp/", "商品・サービス"),
]


@pytest.mark.parametrize('title,description,url,expected', REAL_COMPANY_METADATA)
def test_real_company_titles_have_useful_purpose(title, description, url, expected):
    result = classify_page(title=title, description=description, url=url)
    assert result.category == expected
    assert result.rationale
    assert result.category in CATEGORIES


@pytest.mark.parametrize('title,description,url,expected', [
    ('採用情報 | サイボウズ', 'エンジニアの応募について', 'https://example.com/recruit/', '採用・求人'),
    ('当社の採用募集について', '勤務条件や採用応募', 'https://example.com/jobs/', '採用・求人'),
    ('ニュースリリース | さくらインターネット', '新たな製品を発表', 'https://example.com/news/', 'ニュース・記事'),
    ('新サービス提供開始のお知らせ', '企業向けサービスのお知らせ', 'https://example.com/news/2027/01/01', 'ニュース・記事'),
    ('料金プラン | 管理クラウド', '法人向けサービスの機能と月額料金', 'https://example.com/product/pricing', '商品・サービス'),
    ('サービス | 運用クラウド', '新サービスのご案内', 'https://example.com/', '商品・サービス'),
    ('週末マルシェのお知らせ', '出店募集、開催日時の案内', 'https://example.com/events/', 'イベント'),
    ('焼き菓子専門店 | 月あかり', '販売するタルトとクッキー', 'https://example.com/cafe', '飲食・店舗'),
    ('歴史資料館 | まちの施設', '施設の展示と見学について', 'https://example.com/museum', '観光・施設'),
    ('個人情報保護方針', 'プライバシーポリシー', 'https://example.com/privacy', 'その他'),
])
def test_purpose_is_not_company_industry(title, description, url, expected):
    result = classify_page(title=title, description=description, url=url)
    assert result.category == expected, result


def test_ambiguous_text_abstains():
    result = classify_page(title='資料公開', description='関連情報を掲載しています。')
    assert result.category == 'その他'
    assert result.needs_review
    assert '要確認' in result.rationale


def test_no_company_label_only_because_name_contains_inc():
    result = classify_page(title='新技術について', description='サービスの提供を開始しました', url='https://example.com/news/2026')
    assert result.category == 'ニュース・記事'
    assert result.method == 'URL構造による分類'
    assert result.needs_review


def test_classification_export_has_rationale_and_manual_override():
    html='<html><head><title>企業概要 | テスト株式会社</title><meta name="description" content="代表者・所在地・企業情報"></head><body><h1>企業情報</h1></body></html>'
    rows,errors=process_sources([('co',html,'https://example.com/company/','web-url')])
    assert not errors and len(rows)==1
    assert rows[0].category=='企業・団体'
    original=rows[0].display_dict()
    assert original['分類根拠']=='タイトルの「企業概要」'
    assert original['分類方法']=='明示語句による分類'
    original['カテゴリ']='商品・サービス'
    reviewed=apply_review(rows,[original])
    csvdata=next(csv.DictReader(StringIO(to_csv_bytes(reviewed).decode('utf-8-sig'))))
    assert csvdata['カテゴリ']=='商品・サービス'
    assert csvdata['分類根拠']=='手動修正（自動判定: 企業・団体）'
    assert csvdata['参照URL']=='https://example.com/company/'


def test_ambiguous_result_is_visible_as_review_note():
    html='<html><head><title>資料公開</title><meta name="description" content="資料を掲載しています"></head><body><main>資料</main></body></html>'
    records,errors=process_sources([('x',html,'','uploaded-html')])
    assert not errors and len(records)==1
    assert records[0].category=='その他'
    assert 'カテゴリを確認' in records[0].review_note
    assert records[0].review_status=='要確認'


def test_legacy_sample_labels_remain_valid_after_taxonomy_change(samples):
    rows=[(m['id'],html,m['url'],'demo-html') for m,html in samples]
    records,errors=process_sources(rows)
    assert not errors
    assert [r.category for r in records]==[m['expected_category'] for m,_ in samples]


def test_all_categories_have_seed_examples():
    assert set(TRAINING_SAMPLES)==set(CATEGORIES)
    assert all(len(values)>=10 for values in TRAINING_SAMPLES.values())
