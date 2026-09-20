"""Outgoing mail. ConsoleMailer (the default) just logs the message, which
is enough for development and for the test suite (test_auth.py recovers the
password-reset token from the log line). ResendMailer sends through Resend's
HTTP API once RESEND_API_KEY is configured; get_mailer() picks between them
without any call site changing.
"""
import logging
from typing import Protocol

import httpx

from .config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleMailer:
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("mail to=%s subject=%s body=%s", to, subject, body)


class ResendMailer:
    """Sends through https://api.resend.com/emails. A fresh httpx.AsyncClient
    per call, not a shared one held for the process lifetime: mail is sent
    rarely enough (invitations, password resets) that connection reuse is
    not worth the extra lifecycle to manage, and it keeps this class trivial
    to unit-test with httpx.MockTransport (see tests/test_mail.py)."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def send(self, to: str, subject: str, body: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": settings.mail_from,
                    "to": to,
                    "subject": subject,
                    "text": body,
                },
            )
            response.raise_for_status()


def get_mailer() -> Mailer:
    if settings.resend_api_key:
        return ResendMailer(settings.resend_api_key)
    return ConsoleMailer()
