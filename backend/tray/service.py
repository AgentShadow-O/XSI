from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def start_background_server() -> subprocess.Popen:
    flags = 0
    if sys.platform.startswith("win"):
        flags = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [sys.executable, "-m", "backend.main"],
        cwd=str(ROOT_DIR),
        creationflags=flags,
    )
