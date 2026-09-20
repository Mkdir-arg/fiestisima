"""Outgoing mail. ConsoleMailer (the default) just logs the message, which
is enough for development and for the test suite (test_auth.py recovers the
password-reset token from the log line). Task 4 is expected to add a
ResendMailer that get_mailer() switches to once RESEND_API_KEY is set,
without changing the Mailer interface or any call site.
"""
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleMailer:
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("mail to=%s subject=%s body=%s", to, subject, body)


def get_mailer() -> Mailer:
    return ConsoleMailer()
