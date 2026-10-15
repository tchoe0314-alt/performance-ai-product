"""Explicit node/cell domains and piecewise-linear cut/fill integration.

No resampling, CRS/datum conversion or inference of an ambiguous legacy raster.
Returned volumes are in the cube of the supplied coordinate unit.
"""
import math

METHOD_VERSION = "grid_triangle_cutfill_v2"


def validate_grid(surface):
    for key in ("nrows", "ncols"):
        value = getattr(surface, key, None)
        if type(value) is not int or value < 1:
            raise ValueError(f"{key} must be a positive integer.")
    for key in ("x_min", "x_max", "y_min", "y_max", "cell_size"):
        value = getattr(surface, key, None)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{key} must be finite.")
    if surface.cell_size <= 0:
        raise ValueError("cell_size must be positive.")
    sampling = getattr(surface, "sampling", "nodes")
    if sampling not in ("nodes", "cells"):
        raise ValueError("Surface sampling is unknown; explicitly classify nodes or cells before calculation.")
    offset = 1 if sampling == "nodes" else 0
    for lower, upper, count, field in ((surface.x_min,surface.x_max,surface.ncols,"x"), (surface.y_min,surface.y_max,surface.nrows,"y")):
        expected = (count-offset)*surface.cell_size
        if expected <= 0 or not math.isclose(upper-lower,expected,rel_tol=1e-10,abs_tol=1e-8):
            raise ValueError(f"{field} bounds conflict with {sampling} sampling/spacing; legacy interpretation requires confirmation.")
    if not isinstance(surface.values,(list,tuple)) or len(surface.values)!=surface.nrows:
        raise ValueError("Surface row count is inconsistent.")
    for row in surface.values:
        if not isinstance(row,(list,tuple)) or len(row)!=surface.ncols:
            raise ValueError("Surface column count is inconsistent.")
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in row):
            raise ValueError("Surface has invalid/NoData elevations; complete-domain volume cannot be computed.")
    registration = getattr(surface,"registration",{})
    if not isinstance(registration,dict):
        raise ValueError("Surface registration must be an object.")
    # The current GridSurface has an axis-aligned square-cell interface only.
    if registration.get("affine") is not None:
        raise ValueError("Affine/rotated rasters require explicit transformation to a supported grid before integration.")
    if any(registration.get(key) for key in ("boundary", "holes", "clip_polygon")):
        raise ValueError("Boundary-clipped/holed integration requires a prepared supported domain; full-grid integration is not permitted.")


def validate_pair(existing,proposed):
    validate_grid(existing);validate_grid(proposed)
    for field in ("nrows","ncols","sampling"):
        if getattr(existing,field,"nodes")!=getattr(proposed,field,"nodes"):
            raise ValueError(f"Surface {field} mismatch; explicit resampling required.")
    for field in ("x_min","y_min","x_max","y_max","cell_size"):
        if not math.isclose(getattr(existing,field),getattr(proposed,field),rel_tol=0,abs_tol=1e-8):
            raise ValueError(f"Surface {field} mismatch; grids are not spatially aligned.")
    a=getattr(existing,"registration",{});b=getattr(proposed,"registration",{})
    for key in ("horizontal_crs","horizontal_units","vertical_units","vertical_datum","axis_order"):
        if a.get(key)!=b.get(key):
            raise ValueError(f"Surface {key} mismatch/unknown; an explicit reviewed transform is required.")


def _positive_volume(vertices):
    """Clip linear-height triangle at z=0, integrate a triangle fan exactly."""
    polygon=[]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        if a[2]>=0:polygon.append(a)
        if (a[2]<0)!=(b[2]<0):
            ratio=a[2]/(a[2]-b[2])
            polygon.append((a[0]+ratio*(b[0]-a[0]),a[1]+ratio*(b[1]-a[1]),0.0))
    total=0.0
    for i in range(1,len(polygon)-1):
        a,b,c=polygon[0],polygon[i],polygon[i+1]
        area=abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2
        total+=area*(a[2]+b[2]+c[2])/3
    return total


def integrated_cells(existing,proposed,*,strip_depth=0.0):
    validate_pair(existing,proposed)
    if type(strip_depth) not in (int,float) or not math.isfinite(strip_depth) or strip_depth<0:
        raise ValueError("Strip depth must be finite and nonnegative.")
    size=existing.cell_size;sampling=getattr(existing,"sampling","nodes")
    node_grid=sampling=="nodes"
    for row in range(existing.nrows-(1 if node_grid else 0)):
        for col in range(existing.ncols-(1 if node_grid else 0)):
            indices=[(row,col),(row,col+1),(row+1,col+1),(row+1,col)] if node_grid else [(row,col)]
            ex=[float(existing.values[r][c]) for r,c in indices]
            pr=[float(proposed.values[r][c]) for r,c in indices]
            dz=[p-e+strip_depth for e,p in zip(ex,pr)]
            if node_grid:
                vertices=[(0.,0.,dz[0]),(size,0.,dz[1]),(size,size,dz[2]),(0.,size,dz[3])]
                triangles=[[vertices[0],vertices[1],vertices[2]],[vertices[0],vertices[2],vertices[3]]]
                fill=math.fsum(_positive_volume(t) for t in triangles)
                cut=math.fsum(_positive_volume([(x,y,-z) for x,y,z in t]) for t in triangles)
            else:
                fill=max(dz[0],0)*size**2;cut=max(-dz[0],0)*size**2
            if not math.isfinite(fill+cut):raise ValueError("Surface volume exceeds finite numeric range.")
            yield {"row":row,"col":col,"existing":sum(ex)/len(ex),"proposed":sum(pr)/len(pr),
                   "delta":sum(dz)/len(dz),"area":size**2,"cut":cut,"fill":fill,
                   "max_cut_depth":max(0.,-min(dz)),"max_fill_depth":max(0.,max(dz))}


def cut_fill(existing,proposed):
    cells=list(integrated_cells(existing,proposed))
    cut=math.fsum(c["cut"] for c in cells);fill=math.fsum(c["fill"] for c in cells)
    return cut,fill,fill-cut
