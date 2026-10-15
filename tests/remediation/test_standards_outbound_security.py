from types import SimpleNamespace

import pytest

from backend.planning.standards_discovery import fetch_and_extract_rule_candidates
from backend.services.outbound_http import MAX_BYTES, SafeResponse, safe_get


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "https://127.0.0.1/", "https://169.254.169.254/", "file:///etc/passwd", "https://10.0.0.1/"])
def test_standards_rejects_private_urls_before_transport(url):
    class Unexpected:
        def get(self, *args, **kwargs):
            pytest.fail("Unsafe standards destination reached transport")
    result = fetch_and_extract_rule_candidates(url, session=Unexpected())
    assert result["success"] is False
    assert result["candidate_rules"] == []


def test_text_transport_keeps_bounded_unicode_and_verified_url():
    session = SimpleNamespace(get=lambda *a, **kw: SimpleNamespace(text="Slope ≤ 5%", headers={"content-type": "text/html"}, raise_for_status=lambda: None))
    response = safe_get("https://example.test/standards", session=session, response_kind="text")
    assert response.text == "Slope ≤ 5%"
    assert response.url == "https://example.test/standards"
    assert response.headers["content-type"].startswith("text/html")


def test_text_transport_rejects_oversized_response():
    session = SimpleNamespace(get=lambda *a, **kw: SimpleNamespace(text="x" * (MAX_BYTES + 1), headers={}, raise_for_status=lambda: None))
    with pytest.raises(ValueError, match="too large"):
        safe_get("https://example.test/standards", session=session, response_kind="text")


def test_text_decoding_respects_charset_and_handles_unknown_charset():
    assert SafeResponse(200,b"caf\xe9",{"content-type":"text/plain; charset=iso-8859-1"}).text == "café"
    assert SafeResponse(200,b"hello",{"content-type":"text/plain; charset=unknown-encoding"}).text == "hello"
