"""Offline SSRF boundary tests. DNS, TLS transport and clocks are test doubles."""
import io
import socket
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services.outbound_http import UnsafeDestination, _bounded_lookup, safe_get, validate_destination


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


class OutboundSecurityTests(unittest.TestCase):
    def test_private_transition_and_mixed_answers_are_rejected(self):
        for host in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "[::1]",
                     "[::ffff:127.0.0.1]", "[64:ff9b::a00:1]", "[2002:a00:1::]"):
            with self.subTest(host=host), self.assertRaises(UnsafeDestination):
                validate_destination("https://"+host, resolver=public_dns)
        mixed = lambda *a, **k: public_dns()+[(2,1,6,"",("10.0.0.1",443))]
        with self.assertRaises(UnsafeDestination):
            validate_destination("https://example.test", resolver=mixed)

    def test_url_policy(self):
        for url in ("file:///etc/passwd", "http://example.test", "https://user:pass@example.test",
                    "https://example.test:8443", "https://example.test/\r\nInjected", "https://example.test/#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_destination(url, resolver=public_dns)

    def test_dns_deadline_and_saturation_fail_closed(self):
        release = threading.Event()
        semaphore = threading.BoundedSemaphore(1)
        def slow(*args, **kwargs):
            release.wait(1)
            return public_dns()
        try:
            with patch("backend.services.outbound_http._DNS_SLOTS", semaphore), patch("backend.services.outbound_http.socket.getaddrinfo", slow):
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    _bounded_lookup("example.test", .01)
                with self.assertRaisesRegex(TimeoutError, "budget"):
                    _bounded_lookup("example.test", .01)
                release.set()
                self.assertTrue(semaphore.acquire(timeout=1))
                semaphore.release()
        finally:
            release.set()

    def test_public_request_pins_address_but_preserves_tls_host(self):
        seen = []
        class Connection:
            def __init__(self, host, **kwargs):
                seen.append(("tls", host)); self.sock = None
            def request(self, *args, **kwargs):
                self._create_connection(("example.test",443), 1)
            def getresponse(self):
                data = io.BytesIO(b'{"ok":true}')
                return SimpleNamespace(status=200,getheader=lambda key,default=None:default,
                                       getheaders=lambda:[],read1=data.read)
            def close(self): pass
        with patch("backend.services.outbound_http.http.client.HTTPSConnection", Connection), patch("backend.services.outbound_http.socket.create_connection", side_effect=lambda address,*a:seen.append(("connect",address))):
            response = safe_get("https://example.test/path", resolver=public_dns)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(seen, [("tls","example.test"),("connect",("93.184.216.34",443))])

    def test_redirect_to_private_and_oversized_content_rejected(self):
        class Connection:
            response = None
            def __init__(self, *args, **kwargs): self.sock=None
            def request(self, *args, **kwargs): pass
            def getresponse(self): return self.response
            def close(self): pass
        Connection.response = SimpleNamespace(status=302,getheader=lambda key: "https://127.0.0.1/private")
        with patch("backend.services.outbound_http.http.client.HTTPSConnection",Connection), self.assertRaises(UnsafeDestination):
            safe_get("https://example.test",resolver=public_dns)
        Connection.response = SimpleNamespace(status=200,getheader=lambda key,default=None: str(3*1024*1024) if key=="Content-Length" else default)
        with patch("backend.services.outbound_http.http.client.HTTPSConnection",Connection), self.assertRaisesRegex(ValueError,"large"):
            safe_get("https://example.test",resolver=public_dns)


if __name__ == "__main__":
    unittest.main()
