"""SMTP profile persistence using the OS credential store."""

import json
from pathlib import Path

import keyring

SERVICE = "send_email_gui"
PROFILE_FILE = Path.home() / ".send_email_profiles.json"


def _load() -> dict[str, dict]:
    if not PROFILE_FILE.exists():
        return {}
    try:
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def names() -> list[str]:
    return sorted(_load())


def get(name: str) -> dict:
    profiles = _load()
    profile = dict(profiles.get(name, {}))
    profile["password"] = keyring.get_password(SERVICE, name) or ""
    return profile


def save(name: str, profile: dict) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Profile name cannot be empty")
    profiles = _load()
    public = {k: v for k, v in profile.items() if k != "password"}
    profiles[name] = public
    PROFILE_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    keyring.set_password(SERVICE, name, profile.get("password", ""))


def remove(name: str) -> None:
    profiles = _load()
    profiles.pop(name, None)
    PROFILE_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
