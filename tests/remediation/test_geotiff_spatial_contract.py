"""Tiny authored raster fixtures; all source files are disposable test data."""
import numpy as np
import rasterio
import pytest
from rasterio.transform import Affine, from_origin

from backend.planning.existing_conditions_importers import import_geotiff_surface
from engines.surface_engine import compare_surfaces
from engines.surface_integration import cut_fill


def write_raster(path, values, *, transform=None, nodata=None):
    array=np.array(values,dtype="float32")
    with rasterio.open(path,"w",driver="GTiff",width=array.shape[1],height=array.shape[0],count=1,
                       dtype="float32",crs="EPSG:32614",transform=transform or from_origin(100,220,10,10),nodata=nodata) as dataset:
        dataset.write(array,1)


def test_pixel_extent_centers_and_north_up_row_orientation(tmp_path):
    path=tmp_path/"authored.tif"
    write_raster(path,[[1,2],[3,4]])
    result=import_geotiff_surface(path,coordinate_system={"vertical_units":"m","vertical_datum":"synthetic-local"})
    assert result["success"],result
    surface=result["surface"]
    assert surface.sampling == "cells"
    assert surface.bounds() == (100.0,200.0,120.0,220.0)
    assert surface.values == [[3.0,4.0],[1.0,2.0]]
    assert (surface.x_at(0),surface.y_at(0)) == (105.0,205.0)
    assert surface.registration["horizontal_crs"] == "EPSG:32614"
    assert surface.registration["vertical_datum"] == "synthetic-local"
    assert surface.registration["verified"] is False
    raised=surface.copy()
    raised.values=[[value+1 for value in row] for row in surface.values]
    assert cut_fill(surface,raised)[1] == 400.0  # numeric native unit cubed
    with pytest.raises(ValueError,match="non-foot"):
        compare_surfaces(surface,raised)  # must not label400m3 as400ft3


def test_nodata_never_becomes_invented_mean_elevation(tmp_path):
    path=tmp_path/"missing.tif"
    write_raster(path,[[1,2],[-9999,4]],nodata=-9999)
    result=import_geotiff_surface(path)
    assert result["success"] is False
    assert result["metadata_only"] is True
    assert "surface" not in result
    assert "NoData" in " ".join(result["warnings"])


def test_unsupported_affine_and_non_square_cells_fail_explicitly(tmp_path):
    for index,transform in enumerate((Affine(10,1,100,0,-10,220),from_origin(100,220,10,20))):
        path=tmp_path/f"unsupported-{index}.tif"
        write_raster(path,[[1,2],[3,4]],transform=transform)
        result=import_geotiff_surface(path)
        assert result["success"] is False
        assert result["metadata_only"] is True
