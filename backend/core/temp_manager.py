from __future__ import annotations

import logging
import os
import stat
import tempfile
from pathlib import Path


logger = logging.getLogger("xsi.temp")


def get_temp_directory() -> Path:
    try:
        system_temp = Path(tempfile.gettempdir()).resolve()
        if ensure_directory_permissions(system_temp):
            return system_temp
    except Exception as exc:
        logger.warning("System temp directory unavailable: %s", exc)

    fallback = Path(r"C:\ProgramData\XSI\temp") if os.name == "nt" else Path("/var/lib/xsi/temp")
    if ensure_directory_permissions(fallback):
        return fallback
    raise RuntimeError(f"No writable XSI temporary directory is available; last fallback was {fallback}")


def ensure_directory_permissions(path: str | Path) -> bool:
    directory = Path(path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.is_dir():
            return False
        _harden_permissions(directory)
        test_file = directory / ".xsi_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception as exc:
        logger.warning("Temp directory permission check failed for %s: %s", directory, exc)
        return False


def _harden_permissions(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory.chmod(stat.S_IRWXU)
    except PermissionError:
        logger.warning("Unable to chmod temp directory %s", directory)
