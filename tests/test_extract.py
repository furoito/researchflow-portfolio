import pytest

from researchflow.extract import MAX_HTML_CHARS, extract_page, extracted_summary


def test_six_fixture_pages_extract(samples):
    for meta, html in samples:
        page = extract_page(html, source_id=meta["id"], source_url=meta["url"])
        assert page.title
        assert page.description
        assert page.heading
        assert "デモ用の架空ページ" not in page.body
        assert page.source_url == meta["url"]
        assert extracted_summary(page) == page.description[:100] + ("…" if len(page.description) > 100 else "")


def test_event_page_keeps_event_category_evidence(samples):
    meta, html = next((meta, html) for meta, html in samples if meta["id"] == "05_market")
    page = extract_page(html, source_id=meta["id"])
    assert "マルシェ" in page.title
    assert "開催" in page.body or "開催" in page.description


def test_empty_html_fails():
    with pytest.raises(ValueError, match="HTMLが空"):
        extract_page("  ", source_id="empty")


def test_oversized_html_fails():
    with pytest.raises(ValueError, match="大きすぎ"):
        extract_page("<p>" + "a" * MAX_HTML_CHARS + "</p>", source_id="huge")


def test_script_and_navigation_do_not_pollute_body():
    html = '<html><head><title>小さな喫茶店</title></head><body><nav>SECRET-NAV</nav><main>コーヒーを販売<script>SECRET-SCRIPT</script></main></body></html>'
    page = extract_page(html, source_id="input")
    assert "SECRET" not in page.body
    assert "コーヒー" in page.body


def test_malformed_jsonld_does_not_crash():
    html = '<html><head><title>観光スポット</title><script type="application/ld+json">{{</script></head><body><main>景観を楽しむ</main></body></html>'
    page = extract_page(html, source_id="input")
    assert page.title == "観光スポット"
