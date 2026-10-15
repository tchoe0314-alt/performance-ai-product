from types import SimpleNamespace

import pytest

from backend.planning.worldwide_source_discovery import _get_json
from backend.services.outbound_http import UnsafeDestination


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "https://127.0.0.1/", "https://169.254.169.254/", "https://10.0.0.1/", "file:///etc/passwd"])
def test_worldwide_json_blocks_unsafe_endpoints_before_transport(url):
    class Unexpected:
        def get(self, *args, **kwargs):
            pytest.fail("Private endpoint reached transport")
    with pytest.raises(UnsafeDestination):
        _get_json(Unexpected(), url, params={}, timeout=5)


def test_worldwide_json_preserves_query_and_payload():
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(json=lambda: {"elevation": [100.25]}, raise_for_status=lambda: None)
    result = _get_json(SimpleNamespace(get=get), "https://example.test/elevation",
        params={"latitude": "40,41"}, timeout=5)
    assert result == {"elevation": [100.25]}
    assert calls[0][1]["params"] == {"latitude": "40,41"}
    assert calls[0][1]["allow_redirects"] is False
