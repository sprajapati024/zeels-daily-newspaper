"""Load specific keys from /root/.hermes/.env without ever logging values."""
from __future__ import annotations

from pathlib import Path

HERMES_ENV_PATH = Path("/root/.hermes/.env")


def load_env_keys(keys: tuple[str, ...], env_path: Path | None = None) -> dict[str, str]:
    """Return only the requested keys found in the env file. Missing keys are omitted."""
    if env_path is None:
        env_path = HERMES_ENV_PATH
    wanted = set(keys)
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in wanted:
            out[key] = value.strip().strip('"').strip("'")
    return out
