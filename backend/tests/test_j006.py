"""Real photos: count check against labels counted by eye (SPEC §13). Never shown or committed."""
from __future__ import annotations

import json

import cv2
import pytest

from app.analysis.engine import analyze
from app.analysis.summary import summarize
from app.config import FIXTURES_DIR

J006 = FIXTURES_DIR / "real" / "j006"
LABELS = J006 / "labels.json"

pytestmark = pytest.mark.skipif(not LABELS.exists(), reason="fixtures/real/j006 is not present")


def test_count_matches_labels():
    labels = json.loads(LABELS.read_text())
    rows = []
    for item in labels["images"]:
        path = J006 / item["file"]
        result = analyze(cv2.imread(str(path)))
        s = summarize(result.detections, result.um_per_px)
        rows.append((item["file"], item["larvae_whole"], s.n_live + s.n_abnormal + s.n_dead, s.n_ignored, result.ms))
    exact = sum(1 for _, want, got, _, _ in rows if want == got)
    print(f"\nJ006 exact count on {exact} of {len(rows)} images")
    for name, want, got, ignored, ms in rows:
        flag = "" if want == got else "  <-- off"
        print(f"  {name:<24} labelled {want}  counted {got}  ignored {ignored:>3}  {ms:>5} ms{flag}")
    assert exact >= 20, f"exact on {exact} of {len(rows)}"
