"""Minimal stdlib HTTPS client for the AgentMail v0 inbox send endpoint.

No third-party HTTP dependency: uses urllib.request directly so the
delivery script has no extra runtime surface beyond EbookLib/BeautifulSoup.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

AGENTMAIL_BASE_URL = "https://api.agentmail.to"
SEND_PATH_TEMPLATE = "/v0/inboxes/{inbox_id}/messages/send"

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_BACKOFF_CAP_SECONDS = 8.0
DEFAULT_TIMEOUT_SECONDS = 30


class AgentMailError(Exception):
    """Base error for AgentMail send failures."""


class AgentMailClientError(AgentMailError):
    """Non-retryable 4xx response from AgentMail. Never retried."""

    def __init__(self, status: int, body: str):
        super().__init__(f"AgentMail rejected the request: http {status}")
        self.status = status
        self.body = body


class AgentMailServerError(AgentMailError):
    """5xx response that persisted after all retries were exhausted."""

    def __init__(self, status: int, body: str):
        super().__init__(f"AgentMail server error after retries: http {status}")
        self.status = status
        self.body = body


class AgentMailNetworkError(AgentMailError):
    """Network-level failure that persisted after all retries were exhausted."""


class AgentMailResponseError(AgentMailError):
    """2xx response whose body isn't a parseable JSON object. Never retried."""


@dataclass(frozen=True)
class SendResult:
    message_id: str
    raw: dict


def _build_request(
    *,
    inbox_id: str,
    api_key: str,
    to_email: str,
    subject: str,
    text_body: str,
    filename: str,
    content_bytes: bytes,
    content_type: str,
    idempotency_key: str,
) -> urllib.request.Request:
    url = f"{AGENTMAIL_BASE_URL}{SEND_PATH_TEMPLATE.format(inbox_id=urllib.parse.quote(inbox_id, safe=''))}"
    payload = {
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "attachments": [
            {
                "filename": filename,
                "content_type": content_type,
                "content": base64.b64encode(content_bytes).decode("ascii"),
            }
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        },
    )


def send_epub(
    *,
    api_key: str,
    inbox_id: str,
    to_email: str,
    subject: str,
    text_body: str,
    filename: str,
    content_bytes: bytes,
    content_type: str = "application/epub+zip",
    idempotency_key: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    backoff_cap_seconds: float = DEFAULT_BACKOFF_CAP_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen_fn=urllib.request.urlopen,
    sleep_fn=time.sleep,
) -> SendResult:
    """POST the EPUB to AgentMail. Retries network errors and 5xx only.

    4xx responses are never retried and raise AgentMailClientError immediately.
    """
    request = _build_request(
        inbox_id=inbox_id,
        api_key=api_key,
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        filename=filename,
        content_bytes=content_bytes,
        content_type=content_type,
        idempotency_key=idempotency_key,
    )

    last_network_error: Exception | None = None
    last_server_error: tuple[int, str] | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen_fn(request, timeout=timeout) as response:
                status = response.getcode()
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8", errors="replace")
            if status not in RETRYABLE_STATUS_CODES:
                raise AgentMailClientError(status, body) from exc
            last_server_error = (status, body)
            last_network_error = None
        except urllib.error.URLError as exc:
            last_network_error = exc
            last_server_error = None
        else:
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError as exc:
                raise AgentMailResponseError(f"unparseable response body: {exc}") from exc
            if not isinstance(parsed, dict):
                raise AgentMailResponseError(
                    f"expected a JSON object, got {type(parsed).__name__}"
                )
            message_id = parsed.get("message_id", "")
            return SendResult(message_id=message_id, raw=parsed)

        if attempt < max_attempts:
            delay = min(backoff_seconds * (2 ** (attempt - 1)), backoff_cap_seconds)
            sleep_fn(delay)

    if last_server_error is not None:
        status, body = last_server_error
        raise AgentMailServerError(status, body)
    raise AgentMailNetworkError(str(last_network_error))
