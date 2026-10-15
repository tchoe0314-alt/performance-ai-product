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


@pytest.mark.parametrize("missing", [True, False])
def test_surface_does_not_invent_elevation_for_missing_tile(monkeypatch, missing):
    monkeypatch.setenv("MAPBOX_TOKEN", "synthetic-no-network")
    image = Image.new("RGB", (512,512), (1,2,3))
    calls = []
    def tile(*args):
        calls.append(1)
        return None if missing and len(calls) == 2 else image
    monkeypatch.setattr(terrain, "_fetch_tile", tile)
    surface = terrain.build_terrain_surface(center_lat=40, center_lng=-100,
        lot_x=0, lot_y=0, lot_width_ft=10, lot_height_ft=10,
        rotation_deg=0, x_min=0, y_min=0, ncols=2, nrows=2, cell=10)
    assert len(calls) == (2 if missing else 4)
    if missing:
        assert surface is None
    else:
        assert surface is not None
        assert surface._terrain_sample_stats["missing_count"] == 0
        assert surface.values == [[terrain._elevation_from_rgb(1,2,3)] * 2] * 2


@pytest.mark.parametrize("invalid", [{"ncols":1000000}, {"nrows":True}, {"nrows":2.5},
    {"ncols":140,"nrows":140}, {"cell":0}, {"cell":float("nan")},
    {"center_lat":91}, {"center_lng":float("inf")}, {"lot_width_ft":-1}])
def test_invalid_or_excessive_grid_rejected_before_fetch(monkeypatch, invalid):
    monkeypatch.setenv("MAPBOX_TOKEN", "synthetic-no-network")
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid terrain request reached tile fetching")
    monkeypatch.setattr(terrain,"_fetch_tile",unexpected)
    request = dict(center_lat=40, center_lng=-100, lot_x=0, lot_y=0,
        lot_width_ft=10, lot_height_ft=10, rotation_deg=0,
        x_min=0, y_min=0, ncols=2, nrows=2, cell=10)
    assert terrain.build_terrain_surface(**{**request,**invalid}) is None


def test_provider_failure_stops_large_admissible_grid_immediately(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "synthetic-no-network")
    calls = []
    monkeypatch.setattr(terrain,"_fetch_tile",lambda *args:calls.append(1))
    assert terrain.build_terrain_surface(center_lat=40,center_lng=-100,
        lot_x=0,lot_y=0,lot_width_ft=1000,lot_height_ft=1000,
        rotation_deg=0,x_min=0,y_min=0,ncols=100,nrows=100,cell=10) is None
    assert calls == [1]
