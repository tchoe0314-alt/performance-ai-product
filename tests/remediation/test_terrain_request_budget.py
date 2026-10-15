from PIL import Image

from backend.planning import terrain_provider as terrain


def request():
    return dict(center_lat=40,center_lng=-100,lot_x=0,lot_y=0,
        lot_width_ft=10,lot_height_ft=10,rotation_deg=0,
        x_min=0,y_min=0,ncols=2,nrows=2,cell=10)


def test_deadline_exhaustion_stops_sampling_and_propagates_remaining_budget(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN","synthetic-no-network")
    clock=[100.0]
    monkeypatch.setattr(terrain.time,"monotonic",lambda:clock[0])
    calls=[]
    def fetch(*args,**kwargs):
        calls.append(kwargs["timeout_seconds"])
        clock[0] += terrain.TERRAIN_REQUEST_SECONDS + 1
        return Image.new("RGB",(512,512),(1,2,3))
    monkeypatch.setattr(terrain,"_fetch_tile",fetch)
    assert terrain.build_terrain_surface(**request()) is None
    assert calls == [terrain.TERRAIN_REQUEST_SECONDS]


def test_distinct_tile_limit_stops_before_next_fetch(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN","synthetic-no-network")
    monkeypatch.setattr(terrain,"MAX_TERRAIN_TILES",2)
    sequence=iter([(1,1,0,0),(2,1,0,0),(3,1,0,0),(4,1,0,0)])
    monkeypatch.setattr(terrain,"_lat_lng_to_tile",lambda *args:next(sequence))
    calls=[]
    def fetch(*args,**kwargs):
        calls.append(1)
        return Image.new("RGB",(512,512),(1,2,3))
    monkeypatch.setattr(terrain,"_fetch_tile",fetch)
    assert terrain.build_terrain_surface(**request()) is None
    assert len(calls) == 2
