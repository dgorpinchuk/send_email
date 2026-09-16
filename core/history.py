"""Persistent campaign history and per-campaign log files."""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def _data_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "send_email"
    elif system == "Windows":
        path = Path(os.environ.get("APPDATA", Path.home())) / "send_email"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "send_email"
    path.mkdir(parents=True, exist_ok=True)
    return path


HISTORY_FILE = _data_dir() / "history.json"
LOG_DIR = _data_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        value = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write(items: list[dict]) -> None:
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[:100], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(HISTORY_FILE)


def start(profile: str, subject: str, sender: str, template: str, recipient_file: str, total: int) -> dict:
    campaign_id = uuid4().hex
    now = datetime.now().astimezone()
    log_path = LOG_DIR / f"{now:%Y%m%d_%H%M%S}_{campaign_id[:8]}.log"
    entry = {
        "id": campaign_id,
        "started_at": now.isoformat(timespec="seconds"),
        "finished_at": None,
        "status": "running",
        "profile": profile,
        "subject": subject,
        "sender": sender,
        "template": template,
        "recipient_file": recipient_file,
        "total": total,
        "successful": 0,
        "failed": 0,
        "fatal_error": "",
        "log_file": str(log_path),
    }
    items = _read()
    items.insert(0, entry)
    _write(items)
    log_path.write_text(
        f"Campaign started: {entry['started_at']}\n"
        f"Profile: {profile}\nSubject: {subject}\nTotal: {total}\n\n",
        encoding="utf-8",
    )
    return entry


def append_log(entry: dict, message: str) -> None:
    with Path(entry["log_file"]).open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def finish(entry: dict, successful: int, failed: int, stopped: bool, fatal_error: str = "") -> None:
    now = datetime.now().astimezone()
    if fatal_error:
        status = "failed"
    elif stopped:
        status = "stopped"
    elif failed == 0:
        status = "finished"
    else:
        status = "finished_with_errors"
    entry.update({
        "finished_at": now.isoformat(timespec="seconds"),
        "status": status,
        "successful": successful,
        "failed": failed,
        "fatal_error": fatal_error,
    })
    items = _read()
    for item in items:
        if item.get("id") == entry.get("id"):
            item.update(entry)
            break
    _write(items)
    append_log(entry, f"\nCampaign {status}: {entry['finished_at']}\nSuccessful: {successful}\nErrors: {failed}")
    if fatal_error:
        append_log(entry, f"Fatal error: {fatal_error}")


def list_history() -> list[dict]:
    return _read()
