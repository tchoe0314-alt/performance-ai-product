import pytest
from PIL import Image
from backend.planning import terrain_provider as terrain


def test_known_rgb_metres_convert_to_international_feet_in_grading_surface(monkeypatch):
    # Encoding integer101000 = RGB(1,138,136): provider formula gives100m.
    # One international foot is exactly0.3048m. This is a unit oracle, not
    # evidence of survey accuracy or a geoid transformation.
    assert terrain._elevation_from_rgb(1,138,136) == 100.0
    monkeypatch.setenv("MAPBOX_TOKEN","synthetic-no-network")
    image=Image.new("RGB",(512,512),(1,138,136))
    monkeypatch.setattr(terrain,"_fetch_tile",lambda *a,**kw:image)
    surface=terrain.build_terrain_surface(center_lat=40,center_lng=-100,
        lot_x=0,lot_y=0,lot_width_ft=10,lot_height_ft=10,rotation_deg=0,
        x_min=0,y_min=0,ncols=2,nrows=2,cell=10)
    assert surface.values[0][0] == pytest.approx(328.0839895013123,abs=1e-10)
    assert surface._terrain_sample_stats["source_vertical_units"] == "m"
    assert surface._terrain_sample_stats["control_verified"] is False
