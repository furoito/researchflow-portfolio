"""Deployment contract checks that work without hosting credentials."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_streamlit_entrypoint_and_dependencies():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "st.set_page_config(" in app
    assert "index=2, key=\"input_choice\"" in app
    assert app.count('st.markdown("#### 実装済み")') == 1
    assert "streamlit" in requirements.lower()
    assert (ROOT / ".streamlit" / "config.toml").exists()

def test_local_demo_fixtures_available():
    import json
    fixtures = json.loads((ROOT / "samples" / "index.json").read_text(encoding="utf-8"))
    assert len(fixtures) >= 3
    for item in fixtures:
        assert (ROOT / "samples" / item["file"]).exists()

def test_no_publicly_embedded_gemini_key():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.secrets.get" in app
    assert 'GEMINI_API_KEY = "' not in app
    assert "ENABLE_REMOTE_AI" in app
