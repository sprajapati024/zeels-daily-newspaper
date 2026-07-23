"""Load specific keys from /root/.hermes/.env without ever logging values."""
from __future__ import annotations

from pathlib import Path
import os

HERMES_ENV_PATH = Path("/root/.hermes/.env")


def load_env_keys(keys: tuple[str, ...], env_path: Path | None = None) -> dict[str, str]:
    """Return only the requested keys. Per-call process env wins over the file,
    so callers can override ``KINDLE_SEND_TO_EMAIL`` (or any other key) by
    passing it through the process environment without touching ``.env``."""
    if env_path is None:
        env_path = HERMES_ENV_PATH
    wanted = set(keys)
    out: dict[str, str] = {}
    for key in wanted:
        live = os.environ.get(key)
        if live is not None and live.strip():
            out[key] = live.strip()
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in wanted and key not in out:
            out[key] = value.strip().strip('"').strip("'")
    return out
