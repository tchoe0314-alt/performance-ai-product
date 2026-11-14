"""Explicit, injected email delivery boundary; no network-backed default.

The fake sender is for isolated tests only. It must never be exposed through
an API or used as evidence that a real user controls an email address.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
import os
import smtplib
import ssl
from email.message import EmailMessage as WireMessage
from email.utils import parseaddr


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text: str = field(repr=False)


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class UnconfiguredEmailSender:
    def send(self, message: EmailMessage) -> None:
        raise RuntimeError("Email delivery is not configured; no message was sent.")


def _mailbox(value: str) -> str:
    if not value or any(c in value for c in "\r\n"):
        raise ValueError("A single email address is required.")
    name, address = parseaddr(value)
    if name or address != value or address.count("@") != 1 or any(c.isspace() for c in address):
        raise ValueError("A single email address is required.")
    if not all(address.split("@")):
        raise ValueError("A single email address is required.")
    return address


class SMTPEmailSender:
    """Explicit existing SMTP account; TLS is mandatory, delivery never falls back."""

    def __init__(self, *, host, port, username, password, sender, security="starttls"):
        if security not in ("starttls", "ssl"):
            raise ValueError("SMTP requires starttls or ssl.")
        if not host or any(c.isspace() for c in host) or not username or not password:
            raise ValueError("SMTP account configuration is incomplete.")
        if not 1 <= int(port) <= 65535:
            raise ValueError("Invalid SMTP port.")
        self.host, self.port = host, int(port)
        self.username, self._password = username, password
        self.sender, self.security = _mailbox(sender), security

    def send(self, message: EmailMessage) -> None:
        if not isinstance(message, EmailMessage):
            raise TypeError("Expected an EmailMessage.")
        recipient = _mailbox(message.recipient)
        if any(c in message.subject for c in "\r\n"):
            raise ValueError("Email headers cannot contain line breaks.")
        wire = WireMessage()
        wire["From"], wire["To"], wire["Subject"] = self.sender, recipient, message.subject
        wire.set_content(message.text)
        context = ssl.create_default_context()
        try:
            factory = smtplib.SMTP_SSL if self.security == "ssl" else smtplib.SMTP
            options = {"timeout": 15}
            if self.security == "ssl":
                options["context"] = context
            with factory(self.host, self.port, **options) as client:
                client.ehlo()
                if self.security == "starttls":
                    client.starttls(context=context)
                    client.ehlo()
                client.login(self.username, self._password)
                refused = client.send_message(wire, from_addr=self.sender, to_addrs=[recipient])
                if refused:
                    raise RuntimeError("Recipient refused.")
        except Exception:
            # Provider responses may contain addresses or authentication details.
            raise RuntimeError("Email delivery failed; please retry later.") from None


def configured_email_sender(environ=None) -> EmailSender:
    """No network I/O at startup; only explicit complete SMTP settings activate it."""
    env = os.environ if environ is None else environ
    provider = env.get("CIVORA_EMAIL_PROVIDER", "none").strip().lower()
    if provider == "none":
        return UnconfiguredEmailSender()
    if provider != "smtp":
        raise ValueError("Unsupported email provider.")
    security = env.get("CIVORA_SMTP_SECURITY", "starttls")
    return SMTPEmailSender(
        host=env.get("CIVORA_SMTP_HOST", ""),
        port=env.get("CIVORA_SMTP_PORT", "465" if security == "ssl" else "587"),
        username=env.get("CIVORA_SMTP_USERNAME", ""),
        password=env.get("CIVORA_SMTP_PASSWORD", ""),
        sender=env.get("CIVORA_EMAIL_FROM", ""), security=security)


class FakeEmailSender:
    """In-memory outbox. Explicit construction only; no files or outbound I/O."""

    def __init__(self) -> None:
        self._messages: list[EmailMessage] = []

    @property
    def messages(self) -> tuple[EmailMessage, ...]:
        return tuple(self._messages)

    def send(self, message: EmailMessage) -> None:
        if not isinstance(message, EmailMessage):
            raise TypeError("Expected an EmailMessage.")
        if not message.recipient or "@" not in message.recipient:
            raise ValueError("A recipient email is required.")
        if any(char in message.recipient + message.subject for char in "\r\n"):
            raise ValueError("Email headers cannot contain line breaks.")
        self._messages.append(message)
