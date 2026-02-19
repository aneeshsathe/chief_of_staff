"""Gmail API integration - read unread emails for a single account."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from cos.core.errors import IntegrationError
from cos.core.types import EmailMessage
from cos.integrations.registry import HealthStatus, IntegrationHealth, registry

log = structlog.get_logger("integrations.gmail")


class GmailClient:
    """Gmail API client for reading emails."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, credentials: Credentials, account_id: str = "default") -> None:
        self.account_id = account_id
        self.credentials = credentials
        self._service = build("gmail", "v1", credentials=credentials)

    async def get_unread_emails(self, max_results: int = 50) -> list[EmailMessage]:
        """Fetch unread emails from the inbox."""
        try:
            results = (
                self._service.users()
                .messages()
                .list(userId="me", q="is:unread in:inbox", maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            emails = []
            for msg_ref in messages:
                email = await self._get_message(msg_ref["id"])
                if email:
                    emails.append(email)
            return emails
        except Exception as e:
            raise IntegrationError(f"Gmail fetch failed for {self.account_id}: {e}") from e

    async def _get_message(self, message_id: str) -> EmailMessage | None:
        """Fetch and parse a single email message."""
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}

            body = self._extract_body(msg["payload"])
            date_str = headers.get("date", "")
            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.now(UTC)

            return EmailMessage(
                id=message_id,
                account_id=self.account_id,
                sender=headers.get("from", ""),
                sender_name=headers.get("from", "").split("<")[0].strip().strip('"'),
                to=self._parse_addresses(headers.get("to", "")),
                cc=self._parse_addresses(headers.get("cc", "")),
                subject=headers.get("subject", "(no subject)"),
                body=body,
                snippet=msg.get("snippet", ""),
                date=date,
                thread_id=msg.get("threadId", ""),
                labels=msg.get("labelIds", []),
                is_unread="UNREAD" in msg.get("labelIds", []),
            )
        except Exception as e:
            log.debug("Failed to parse message", message_id=message_id, error=str(e))
            return None

    def _extract_body(self, payload: dict) -> str:
        """Extract plain text body from email payload."""
        if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="replace"
                )
            # Recurse into multipart
            if part.get("parts"):
                result = self._extract_body(part)
                if result:
                    return result
        return ""

    @staticmethod
    def _parse_addresses(header: str) -> list[str]:
        if not header:
            return []
        return [addr.strip() for addr in header.split(",")]


async def _gmail_health_check() -> IntegrationHealth:
    return IntegrationHealth(
        name="gmail", status=HealthStatus.UNCONFIGURED, message="Run 'cos config init' to set up"
    )


registry.register("gmail", _gmail_health_check)
