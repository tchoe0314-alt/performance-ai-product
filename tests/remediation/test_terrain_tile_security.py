from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.planning import terrain_provider as terrain
from backend.services.outbound_http import MAX_BYTES, SafeResponse, safe_get


def png(size=(512,512), mode="RGB", color=(1,2,3)):
    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("content", [b"not an image", png((1,1)), png((1024,1024)), png(mode="RGBA",color=(1,2,3,0))])
def test_malformed_or_unexpected_tile_is_not_cached(monkeypatch, content):
    monkeypatch.setattr(terrain,"safe_get",lambda *a,**kw: SafeResponse(200,content,{}))
    cache = {}
    assert terrain._fetch_tile("synthetic-token", 1, 1, 14, cache) is None
    assert cache == {}


def test_valid_tile_decodes_once_and_caches(monkeypatch):
    calls = []
    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return SafeResponse(200,png(),{})
    monkeypatch.setattr(terrain,"safe_get",fetch)
    cache = {}
    image = terrain._fetch_tile("synthetic-token",1,1,14,cache)
    assert image.size == (512,512)
    assert image.getpixel((0,0)) == (1,2,3)
    assert terrain._fetch_tile("synthetic-token",1,1,14,cache) is image
    assert calls == [{"timeout":10,"response_kind":"binary"}]


def test_binary_transport_retains_bytes_and_size_limit():
    for content in (b"\x89PNG\x00\xff", b"x"*(MAX_BYTES+1)):
        session=SimpleNamespace(get=lambda *a,**kw: SimpleNamespace(content=content,raise_for_status=lambda:None))
        if len(content)>MAX_BYTES:
            with pytest.raises(ValueError,match="too large"):
                safe_get("https://example.test/tile",session=session,response_kind="binary")
        else:
            assert safe_get("https://example.test/tile",session=session,response_kind="binary").content == content
