"""Offline SMTP protocol checks. No sockets, paid services or real recipients."""
import ssl
import unittest
from unittest.mock import MagicMock, patch
from backend.services.email_delivery import (
    EmailMessage, SMTPEmailSender, UnconfiguredEmailSender, configured_email_sender,
)


class SMTPTests(unittest.TestCase):
    def sender(self, security='starttls'):
        return SMTPEmailSender(host='smtp.example.test', port=587, username='test',
                               password='secret', sender='sender@example.test', security=security)

    def test_factory_fails_closed(self):
        self.assertIsInstance(configured_email_sender({}), UnconfiguredEmailSender)
        for config in ({'CIVORA_EMAIL_PROVIDER': 'fake'}, {'CIVORA_EMAIL_PROVIDER': 'smtp'}):
            with self.assertRaises(ValueError):
                configured_email_sender(config)

    @patch('backend.services.email_delivery.smtplib.SMTP')
    def test_starttls_before_login_and_explicit_envelope(self, factory):
        client = factory.return_value.__enter__.return_value
        client.send_message.return_value = {}
        self.sender().send(EmailMessage('recipient@example.test', 'Confirmation', 'private-token'))
        self.assertEqual([c[0] for c in client.method_calls],
                         ['ehlo', 'starttls', 'ehlo', 'login', 'send_message'])
        context = client.starttls.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        args = client.send_message.call_args
        self.assertEqual(args.kwargs['to_addrs'], ['recipient@example.test'])
        self.assertEqual(args.kwargs['from_addr'], 'sender@example.test')
        self.assertIn('private-token', args.args[0].get_content())
        self.assertEqual(factory.call_args.kwargs['timeout'], 15)

    @patch('backend.services.email_delivery.smtplib.SMTP_SSL')
    def test_implicit_tls(self, factory):
        client = factory.return_value.__enter__.return_value
        client.send_message.return_value = {}
        self.sender('ssl').send(EmailMessage('recipient@example.test', 'Confirmation', 'test'))
        self.assertTrue(factory.call_args.kwargs['context'].check_hostname)
        client.starttls.assert_not_called()
        client.login.assert_called_once()

    @patch('backend.services.email_delivery.smtplib.SMTP')
    def test_tls_failure_never_authenticates_or_sends(self, factory):
        client = factory.return_value.__enter__.return_value
        client.starttls.side_effect = RuntimeError('secret provider details')
        with self.assertRaisesRegex(RuntimeError, '^Email delivery failed; please retry later.$'):
            self.sender().send(EmailMessage('recipient@example.test', 'Confirmation', 'test'))
        client.login.assert_not_called()
        client.send_message.assert_not_called()

    @patch('backend.services.email_delivery.smtplib.SMTP')
    def test_refused_recipient_is_failure(self, factory):
        factory.return_value.__enter__.return_value.send_message.return_value = {'recipient': (550, b'no')}
        with self.assertRaises(RuntimeError):
            self.sender().send(EmailMessage('recipient@example.test', 'Confirmation', 'test'))

    @patch('backend.services.email_delivery.smtplib.SMTP')
    def test_headers_rejected_before_connection(self, factory):
        for recipient, subject in [('a@example.test,b@example.test','Test'),
                                   ('a@example.test\nBcc:x@example.test','Test'),
                                   ('a@example.test','Test\r\nBcc:x@example.test')]:
            with self.assertRaises(ValueError):
                self.sender().send(EmailMessage(recipient, subject, 'test'))
        factory.assert_not_called()

    def test_plaintext_and_bad_sender_forbidden(self):
        with self.assertRaises(ValueError):
            self.sender('none')
        with self.assertRaises(ValueError):
            SMTPEmailSender(host='smtp.example.test', port=587, username='test',
                            password='secret', sender='a@example.test,b@example.test')

if __name__ == '__main__':
    unittest.main()
