"""Explicit, injected email delivery boundary; no network-backed default.

The fake sender is for isolated tests only. It must never be exposed through
an API or used as evidence that a real user controls an email address.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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
