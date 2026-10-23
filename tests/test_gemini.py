import pytest

from researchflow.gemini import GeminiError, enrich_with_gemini


class FakeResponse:
    def __init__(self, value):
        self.value = value
    def raise_for_status(self):
        pass
    def json(self):
        return self.value


class FakeClient:
    def __init__(self, value):
        self.value = value
        self.last_request = None
    def post(self, url, **kwargs):
        self.last_request = (url, kwargs)
        return FakeResponse(self.value)


def test_gemini_mocked_success():
    client = FakeClient({"candidates": [{"content": {"parts": [{"text": '{"category":"観光・施設","summary":"港を見渡せる展望施設。"}'}]}}]})
    label, summary = enrich_with_gemini("展望", "観光施設の紹介文", api_key="fake", session=client)
    assert (label, summary) == ("観光・施設", "港を見渡せる展望施設。")
    assert client.last_request[1]["headers"]["x-goog-api-key"] == "fake"
    assert client.last_request[1]["timeout"] == (5, 20)


def test_gemini_rejects_invalid_category():
    client = FakeClient({"candidates": [{"content": {"parts": [{"text": '{"category":"架空","summary":"test"}'}]}}]})
    with pytest.raises(GeminiError, match="Gemini分析に失敗"):
        enrich_with_gemini("test", "test", api_key="fake", session=client)


def test_gemini_requires_key():
    with pytest.raises(GeminiError, match="APIキー"):
        enrich_with_gemini("test", "test", api_key="")
