#!/usr/bin/env python3
"""Shirin's Brief newspaper: build, validate and (optionally) deliver.

Reads `/var/www/briefs/<date>.newspaper.json` (schema enforced by
`newspaper_schema.py`) plus the JPEG cover it names, builds a Kindle-safe
EPUB3 newspaper (`newspaper_epub_builder.py`), validates it with the
official epubcheck when installed, and -- only when `--send` is passed --
delivers it via AgentMail using the same env keys and retry/backoff logic
as `morning_brief_epub_deliver.py`.

Usage:
    newspaper_deliver.py <iso-date> --build-only
    newspaper_deliver.py <iso-date> --send

Idempotent: if `<date>.newspaper.delivered` already exists, or the source
`<date>.newspaper.json` is missing, this exits 0 immediately and makes no
changes -- the same convention the existing delivery CLIs use for their
own markers. This is an additional, independent artifact/pipeline: it does
not read, write or touch `<date>.html`, `<date>.epub`, `<date>.epub.delivered`,
or the Telegram/voice pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentmail_client import AgentMailClientError, AgentMailError, send_epub
from cover_image import CoverImageError
from hermes_env import load_env_keys
from zeels_daily_epub_builder import build_epub
from zeels_daily_schema import NewspaperSchemaError, parse_issue
BRIEFS_DIR = Path(os.getenv("MORNING_BRIEFS_DIR", "/var/www/briefs"))
EPUB_SUFFIX = ".zeels-daily.epub"
IDEMPOTENCY_PREFIX = "zeels-daily"
DELIVERED_MARKER_SUFFIX = ".zeels-daily.delivered"
SUBJECT_PREFIX = "Zeel’s Daily"
JSON_SUFFIX = ".zeels-daily.json"
COVER_DEFAULT_FILENAME = ".zeels-daily.cover.jpg"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTENT_TYPE = "application/epub+zip"
ENV_KEYS = ("AGENTMAIL_API_KEY", "AGENTMAIL_INBOX_ID", "KINDLE_SEND_TO_EMAIL")
EPUBCHECK_TIMEOUT_SECONDS = 120


class BuildError(Exception):
    """Raised when the newspaper JSON/cover can't be turned into a valid EPUB."""


def _fail(message: str) -> int:
    print(f"newspaper_deliver: {message}", file=sys.stderr)
    return 1


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _run_epubcheck(epub_path: Path) -> None:
    """Run the official epubcheck if it's on PATH; raise :class:`BuildError`
    on any errors OR warnings (``--failonwarnings``). A no-op, logged to
    stderr, when epubcheck isn't installed.
    """
    binary = shutil.which("epubcheck")
    if binary is None:
        print("newspaper_deliver: epubcheck not found on PATH, skipping validation", file=sys.stderr)
        return
    proc = subprocess.run(
        [binary, "--failonwarnings", str(epub_path)],
        capture_output=True,
        text=True,
        timeout=EPUBCHECK_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip().splitlines()
        tail = "; ".join(detail[-8:])
        raise BuildError(f"epubcheck failed (exit {proc.returncode}): {tail}")


def build_newspaper_epub(iso_date: str, briefs_dir: Path, *, run_epubcheck: bool = True) -> Path:
    """Validate `<date>.newspaper.json` + its cover, build the EPUB, write
    it atomically to `<date>.shirins-brief.epub`, and return that path.
    """
    json_path = briefs_dir / f"{iso_date}{JSON_SUFFIX}"
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"invalid JSON in {json_path}: {exc}") from exc

    issue = parse_issue(raw)
    if issue.metadata.date != iso_date:
        raise BuildError(
            f"issue metadata.date {issue.metadata.date!r} does not match requested date {iso_date!r}"
        )

    cover_path = briefs_dir / issue.cover_image
    try:
        cover_bytes = cover_path.read_bytes()
    except OSError as exc:
        raise BuildError(f"failed to read cover {cover_path}: {exc}") from exc

    epub_bytes = build_epub(issue, cover_bytes)

    epub_path = briefs_dir / f"{iso_date}{EPUB_SUFFIX}"
    _atomic_write(epub_path, epub_bytes)

    if run_epubcheck:
        _run_epubcheck(epub_path)

    return epub_path


def _send(iso_date: str, epub_path: Path, marker_path: Path, idempotency_key: str | None = None) -> int:
    env = load_env_keys(ENV_KEYS)
    missing = [k for k in ENV_KEYS if not env.get(k)]
    if missing:
        return _fail(f"missing required config in /root/.hermes/.env: {', '.join(missing)}")

    epub_bytes = epub_path.read_bytes()
    filename = f"zeels-daily-{iso_date}.epub"
    key = idempotency_key or f"{IDEMPOTENCY_PREFIX}-{iso_date}"

    try:
        result = send_epub(
            api_key=env["AGENTMAIL_API_KEY"],
            inbox_id=env["AGENTMAIL_INBOX_ID"],
            to_email=env["KINDLE_SEND_TO_EMAIL"],
            subject=f"{SUBJECT_PREFIX} — {iso_date}",
            text_body="Your Kindle-ready edition of Zeel’s Daily is attached.",
            filename=filename,
            content_bytes=epub_bytes,
            content_type=CONTENT_TYPE,
            idempotency_key=key,
        )
    except AgentMailClientError as exc:
        return _fail(f"AgentMail rejected the send (http {exc.status}); not retrying")
    except AgentMailError as exc:
        return _fail(f"AgentMail send failed after retries: {exc}")

    marker = {
        "message_id": result.message_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _atomic_write(marker_path, json.dumps(marker, indent=2).encode("utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and optionally deliver the Zeel’s Daily newspaper EPUB."
    )
    parser.add_argument("date", help="ISO date of the issue, e.g. 2026-07-22")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-only", action="store_true", help="Build the EPUB only; do not send")
    mode.add_argument("--send", action="store_true", help="Build the EPUB and send it via AgentMail")
    parser.add_argument(
        "--idempotency-key",
        default=None,
        help="Override the default idempotency key (manual/demo sends only).",
    )
    args = parser.parse_args(argv)

    iso_date = args.date
    if not DATE_RE.match(iso_date):
        return _fail(f"bad iso date: {iso_date!r}")

    marker_path = BRIEFS_DIR / f"{iso_date}{DELIVERED_MARKER_SUFFIX}"
    json_path = BRIEFS_DIR / f"{iso_date}{JSON_SUFFIX}"

    if marker_path.exists():
        return 0
    if not json_path.exists():
        return 0

    try:
        epub_path = build_newspaper_epub(iso_date, BRIEFS_DIR)
    except OSError as exc:
        return _fail(f"failed to write EPUB: {exc}")
    except (NewspaperSchemaError, CoverImageError, BuildError) as exc:
        return _fail(f"failed to build Zeel’s Daily EPUB: {exc}")
    except Exception as exc:
        return _fail(f"failed to build Zeel’s Daily EPUB: {exc}")

    if args.build_only:
        return 0

    return _send(iso_date, epub_path, marker_path, idempotency_key=args.idempotency_key)


if __name__ == "__main__":
    sys.exit(main())
