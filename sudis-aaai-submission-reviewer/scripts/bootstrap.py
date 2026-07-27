#!/usr/bin/env python3
"""Install standalone PDF and rendering dependencies into a local virtual environment."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
subprocess.run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=True)
subprocess.run([str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
print(PYTHON)
