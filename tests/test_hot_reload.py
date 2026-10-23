"""v0.8 hot-reload guard is installed ahead of package symbol imports."""
from pathlib import Path
APP=(Path(__file__).parents[1]/"app.py").read_text(encoding="utf-8")

def test_classifier_hot_reload_guard_precedes_imports():
    assert APP.index("import researchflow.classify as _classify_module") < APP.index("from researchflow.classify import TRAINING_SAMPLES, CATEGORIES")
    assert APP.index("reload(_process_module)") < APP.index("from researchflow.process import process_sources, to_csv_bytes")
    assert 'or "分類根拠" not in _process_module.EXPORT_COLUMNS' in APP
    assert 'tuple(_classify_module.CATEGORIES) != _EXPECTED_CATEGORIES' in APP
