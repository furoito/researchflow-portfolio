from pathlib import Path
import json

import pytest

BASE = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples():
    data = json.loads((BASE / "samples" / "index.json").read_text(encoding="utf-8"))
    return [
        (sample, (BASE / "samples" / sample["file"]).read_text(encoding="utf-8"))
        for sample in data
    ]
