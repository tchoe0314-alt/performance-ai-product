"""Synthetic in-memory delivery boundary tests; no app or database startup."""
import unittest

from backend.services.email_delivery import EmailMessage, FakeEmailSender, UnconfiguredEmailSender


class EmailDeliveryTests(unittest.TestCase):
    def test_fake_captures_without_shared_state(self):
        sender = FakeEmailSender()
        message = EmailMessage("engineer@example.test", "Verify email", "synthetic-token")
        sender.send(message)
        self.assertEqual(sender.messages, (message,))
        self.assertEqual(FakeEmailSender().messages, ())
        self.assertNotIn("synthetic-token", repr(message))

    def test_unconfigured_delivery_fails_closed(self):
        with self.assertRaises(RuntimeError):
            UnconfiguredEmailSender().send(EmailMessage("a@example.test", "Verify", "test"))

    def test_header_injection_and_invalid_recipients_rejected(self):
        sender = FakeEmailSender()
        for recipient, subject in (("", "Verify"), ("invalid", "Verify"),
                                   ("a@example.test\r\nBcc:b@example.test", "Verify"),
                                   ("a@example.test", "Verify\nInjected")):
            with self.subTest(recipient=recipient), self.assertRaises(ValueError):
                sender.send(EmailMessage(recipient, subject, "test"))
        self.assertEqual(sender.messages, ())


if __name__ == "__main__":
    unittest.main()
