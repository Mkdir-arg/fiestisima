"""ResendMailer, unit-tested against httpx.MockTransport - never the real
network. Does not need the database or the app fixtures from conftest.py.
"""
import httpx
import pytest

from app.config import settings
from app.mail import RESEND_API_URL, ConsoleMailer, ResendMailer, get_mailer


async def test_resend_mailer_send_uses_mock_transport(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "email-id"})

    transport = httpx.MockTransport(handler)

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("app.mail.httpx.AsyncClient", _MockAsyncClient)

    mailer = ResendMailer("test-api-key")
    await mailer.send(to="someone@example.invalid", subject="Hello", body="Body text")

    assert captured["url"] == RESEND_API_URL
    assert captured["headers"]["authorization"] == "Bearer test-api-key"
    import json
    payload = json.loads(captured["body"])
    assert payload["to"] == "someone@example.invalid"
    assert payload["subject"] == "Hello"
    assert payload["text"] == "Body text"
    assert payload["from"] == settings.mail_from


async def test_resend_mailer_send_raises_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "bad request"})

    transport = httpx.MockTransport(handler)

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("app.mail.httpx.AsyncClient", _MockAsyncClient)

    mailer = ResendMailer("test-api-key")
    with pytest.raises(httpx.HTTPStatusError):
        await mailer.send(to="someone@example.invalid", subject="Hello", body="Body text")


def test_get_mailer_picks_resend_when_api_key_set(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "some-key")
    assert isinstance(get_mailer(), ResendMailer)


def test_get_mailer_defaults_to_console_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    assert isinstance(get_mailer(), ConsoleMailer)
