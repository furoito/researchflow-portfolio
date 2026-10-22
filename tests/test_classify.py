from researchflow.classify import classify_local, get_model
from researchflow.extract import extract_page


def test_local_model_is_reused():
    assert get_model() is get_model()


def test_fixture_classification(samples):
    actual = {}
    for meta, html in samples:
        page = extract_page(html, source_id=meta["id"])
        category, score = classify_local(page.model_input)
        actual[meta["id"]] = category
        assert 0.0 < score <= 1.0
    assert actual == {meta["id"]: meta["expected_category"] for meta, _ in samples}


def test_empty_input_returns_other():
    assert classify_local("") == ("その他", 0.0)
