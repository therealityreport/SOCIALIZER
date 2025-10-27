from __future__ import annotations

import logging
from typing import Iterable, Sequence

import httpx


logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self, webhook_url: str | None, timeout: float = 5.0) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, text: str, blocks: list[dict[str, object]] | None = None) -> bool:
        if not self.webhook_url:
            logger.info("Slack webhook not configured; skipping alert delivery.")
            return False

        payload: dict[str, object] = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors are best-effort
            logger.error("Slack delivery failed: %s", exc)
            return False

        return True


class SendGridEmailNotifier:
    def __init__(self, api_key: str | None, from_email: str | None, from_name: str | None = None, timeout: float = 5.0) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name or "SOCIALIZER"
        self.timeout = timeout

    def send(self, recipients: Sequence[str], subject: str, html_content: str, plain_content: str | None = None) -> bool:
        if not self.api_key or not self.from_email:
            logger.info("SendGrid not configured; skipping email delivery.")
            return False

        filtered = [email for email in recipients if email]
        if not filtered:
            logger.info("No email recipients provided; skipping email delivery.")
            return False

        payload = {
            "personalizations": [
                {
                    "to": [{"email": email} for email in filtered],
                }
            ],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain_content or html_content},
                {"type": "text/html", "value": html_content},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code not in (200, 202):
                logger.error("SendGrid responded with %s: %s", response.status_code, response.text)
                return False
        except httpx.HTTPError as exc:  # pragma: no cover - network errors are best-effort
            logger.error("SendGrid delivery failed: %s", exc)
            return False

        return True


def format_markdown_list(items: Iterable[str]) -> str:
    return "\n".join(f"• {item}" for item in items)
