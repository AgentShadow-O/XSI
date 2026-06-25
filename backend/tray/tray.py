from __future__ import annotations

import webbrowser

from backend.core.config import API_BASE_URL


def open_dashboard() -> None:
    webbrowser.open(API_BASE_URL)


def status_text() -> str:
    return "XSI Running"
