"""Test setup: no real API key, and every test run uses a temp data folder.

These two lines must run before anything imports `app`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""  # load_dotenv does not override a variable that is already set
_TMP = tempfile.mkdtemp(prefix="thetis-tests-")
os.environ["THETIS_DATA_DIR"] = _TMP

REPO_ROOT = Path(__file__).resolve().parents[2]
