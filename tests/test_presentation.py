"""Protect v0.4 typography-led layout and the original working demo."""
from pathlib import Path
from bs4 import BeautifulSoup
from researchflow.presentation import DEMO_INTRO, FEATURE, HERO, SITE_HEADER, WORKFLOW

ROOT = Path(__file__).resolve().parents[1]


def test_design_is_original_and_shared_with_streamlit():
    css = (ROOT / 'assets/editorial.css').read_text(encoding='utf-8')
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'CSS_FILE.read_text' in app
    assert 'artvibes.co.jp' in css
    assert 'No third-party CSS' in css
    assert 'linear-gradient(' not in css
    assert '.rf-hero h1' in css
    assert '.rf-feature' in css
    assert '.rf-workflow-item' in css
    assert '@media(max-width:700px)' in css


def test_preview_has_actual_processed_rows_and_accessible_controls():
    page = (ROOT / 'preview.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(page, 'html.parser')
    assert len(soup.select('#items tr')) == 6
    assert soup.select_one('#category[aria-label]') is not None
    assert soup.select_one('#search[aria-label]') is not None
    assert soup.select_one("a[download='researchflow_results.csv']") is not None
    assert '<!--RF_' not in page


def test_shared_page_fragments_are_in_preview():
    page = (ROOT / 'preview.html').read_text(encoding='utf-8')
    for part in [SITE_HEADER, HERO, FEATURE, WORKFLOW, DEMO_INTRO]:
        assert part in page


def test_viewer_has_single_h1_and_a_real_demo_destination():
    page = (ROOT / 'preview.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(page, 'html.parser')
    assert len(soup.select('h1')) == 1
    assert soup.select_one('a.rf-action-primary[href="#demo"]') is not None
    assert soup.select_one('.rf-demo-intro#demo') is not None
    assert soup.select_one('section#workflow .rf-workflow-item') is not None
    assert page.index('id="rf-hero-title"') < page.index('id="workflow"') < page.index('id="demo"')
    anchors = {element['id'] for element in soup.select('[id]')}
    for link in soup.select('a[href^="#"]'):
        assert link['href'][1:] in anchors


def test_live_app_has_demo_before_secondary_tabs():
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert app.index('st.markdown(DEMO_INTRO') < app.index('tab_structure, tab_profile = st.tabs(')
    assert 'st.markdown(WORKFLOW' in app
    assert 'SITE_HEADER + HERO + FEATURE' in app
    assert 'class="rf-demo-intro" id="demo"' in DEMO_INTRO


def test_japanese_headings_have_no_sentence_punctuation_and_copy_is_concrete():
    """Keep editorial headings distinct from explanatory body text."""
    soup = BeautifulSoup((ROOT / 'preview.html').read_text(encoding='utf-8'), 'html.parser')
    for heading in soup.select('h1,h2,h3'):
        label = heading.get_text(' ', strip=True)
        assert not any(char in label for char in '。、！？'), label
    content = soup.get_text(' ', strip=True)
    for stale in [
        '情報を拾って',
        '整理すると、こうなる',
        '大きなシステムではなく',
        '小さく自動化',
        'できること、まだできないこと',
        'REAL WORK, NOT JUST A MOCKUP',
    ]:
        assert stale not in content
    assert '公開URLの取得' in content
    assert '実務データでの精度は未検証' in content
