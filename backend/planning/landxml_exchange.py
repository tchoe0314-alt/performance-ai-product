"""Strict LandXML 1.2 exchange for node grids and straight circular networks.

No inferred elevations, inferred connectivity, or native-CAD compatibility claims.
The legacy XML report writer is not used by the artifact export endpoint.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import xml.etree.ElementTree as ET

NS = "http://www.landxml.org/schema/LandXML-1.2"
AUDIT_NS = "https://civoraai.com/schema/exchange/1"
ET.register_namespace("", NS)
ET.register_namespace("civora", AUDIT_NS)


def tag(name):
    return f"{{{NS}}}{name}"


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"LandXML {label} must be an object.")
    return value


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"LandXML needs a finite {label}; missing values are not zero.")
    return float(value)


def pick(rec, *keys):
    return next((rec[k] for k in keys if k in rec and rec[k] is not None), None)


def fmt(value):
    return format(value, ".15g")


def feature(parent, values):
    node = ET.SubElement(parent, tag("Feature"), {"code": "Civora", "source": "Civora"})
    for key, value in values.items():
        ET.SubElement(node, tag("Property"), {"label": key, "value": str(value)})


def snapshot_grid(surface):
    """Persist exact computed nodes; display extrema cannot reconstruct a surface."""
    if surface is None:
        return None
    return {"version": 1, "sampling": surface.sampling, "x_min": surface.x_min,
            "y_min": surface.y_min, "x_max": surface.x_max, "y_max": surface.y_max,
            "cell_size": surface.cell_size, "nrows": surface.nrows, "ncols": surface.ncols,
            "values": [list(row) for row in surface.values],
            "registration": dict(surface.registration)}


def network_geometry_signature(data):
    """Bind exact exchange output to the displayed calculation geometry."""
    keys = {
        "nodes": ("id", "name", "x", "y", "rim_elev_ft", "invert_elev_ft"),
        "segments": ("id", "pipe", "from", "to", "start_name", "end_name", "node_ids",
                     "path", "route_points", "length_ft", "diameter_in", "slope_ft_ft",
                     "start_invert", "end_invert", "start_invert_ft", "end_invert_ft"),
    }
    geometry = {key: [{field: row.get(field) for field in fields} for row in data.get(key, [])]
                for key, fields in keys.items()}
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, allow_nan=False).encode()).hexdigest()


def surface_xml(parent, raw, name):
    raw = mapping(raw, "surface")
    grid = mapping(raw.get("exchange_grid_v1") or raw, "surface grid")
    if grid.get("sampling", "nodes") != "nodes":
        raise ValueError("LandXML node-grid export does not support cell-center surfaces; explicit conversion is required.")
    values = pick(grid, "values", "grid")
    if not isinstance(values, list) or len(values) < 2 or not isinstance(values[0], list) or len(values[0]) < 2:
        raise ValueError(f"LandXML surface {name} has no complete node grid; recalculate grading.")
    rows, cols = len(values), len(values[0])
    if rows * cols > 1_000_000:
        raise ValueError("LandXML surface exceeds the supported one-million-node export budget.")
    if any(not isinstance(row, list) or len(row) != cols for row in values):
        raise ValueError("LandXML surface rows must have matching lengths.")
    if grid.get("nrows", rows) != rows or grid.get("ncols", cols) != cols:
        raise ValueError("LandXML surface grid dimensions disagree with node values.")
    x = number(pick(grid, "x_min", "origin_x"), "surface origin x")
    y = number(pick(grid, "y_min", "origin_y"), "surface origin y")
    step = number(grid.get("cell_size"), "surface cell size")
    if step <= 0:
        raise ValueError("LandXML surface cell size must be positive.")
    for key, expected in (("x_max", x+(cols-1)*step), ("y_max", y+(rows-1)*step)):
        if key in grid and not math.isclose(number(grid[key], key), expected, abs_tol=1e-7, rel_tol=1e-10):
            raise ValueError("LandXML node-grid bounds disagree with sampling dimensions.")
    reg = mapping(grid.get("registration") or {}, "surface registration")
    for key in ("horizontal_units", "vertical_units"):
        if reg.get(key) is not None and reg[key] not in ("ft", "international_foot", "feet", "foot"):
            raise ValueError("LandXML surface units require explicit conversion to international feet.")
    if reg.get("affine") is not None:
        raise ValueError("LandXML affine surface grids need explicit transformation before export.")
    if any(reg.get(key) for key in ("boundary", "holes", "clip_polygon")):
        raise ValueError("LandXML clipped/holed surfaces need supported boundary triangulation; full-grid export is blocked.")
    if reg.get("rotation", 0) or reg.get("rotation_deg", 0):
        raise ValueError("Rotated surface grids need explicit transformation before LandXML export.")
    surf = ET.SubElement(parent, tag("Surface"), {"name": name, "desc": "Review only; computed node grid triangulated along SW-NE diagonals"})
    definition = ET.SubElement(surf, tag("Definition"), {"surfType": "TIN"})
    points, faces = ET.SubElement(definition, tag("Pnts")), ET.SubElement(definition, tag("Faces"))
    for r, row in enumerate(values):
        for c, z in enumerate(row):
            # LandXML position order is northing, easting, elevation.
            ET.SubElement(points, tag("P"), {"id": str(r*cols+c+1)}).text = f"{fmt(y+r*step)} {fmt(x+c*step)} {fmt(number(z, 'surface elevation'))}"
    for r in range(rows-1):
        for c in range(cols-1):
            a = r*cols+c+1
            for face in ((a, a+1, a+cols+1), (a, a+cols+1, a+cols)):
                ET.SubElement(faces, tag("F")).text = " ".join(map(str, face))


def build_landxml_exchange(plan, *, network_name="Civora Pipe Network"):
    if str(plan.get("units", "")).lower() not in {"ft", "feet"}:
        raise ValueError("LandXML exchange currently requires explicit international feet; survey feet and metric require an explicit conversion.")
    meta = mapping(plan.get("meta") or {}, "metadata")
    coordinates = mapping(meta.get("coordinate_system") or {}, "coordinate system")
    for key in ("horizontal_units", "vertical_units", "linear_units"):
        if coordinates.get(key) and str(coordinates[key]).lower() not in {"ft", "feet", "foot"}:
            raise ValueError("LandXML coordinate units conflict with international feet; explicit conversion is required.")
    now = datetime.now(timezone.utc)
    root = ET.Element(tag("LandXML"), {"version": "1.2", "date": now.date().isoformat(), "time": now.time().replace(tzinfo=None).isoformat(timespec="seconds")})
    units = ET.SubElement(root, tag("Units"))
    ET.SubElement(units, tag("Imperial"), {"linearUnit": "foot", "areaUnit": "squareFoot", "volumeUnit": "cubicFeet", "temperatureUnit": "fahrenheit", "pressureUnit": "inHG", "diameterUnit": "foot", "elevationUnit": "feet"})
    if coordinates:
        attrs = {"desc": "User-provided coordinate reference; no transformation or survey verification performed"}
        for source, target in (("horizontal_crs", "horizontalCoordinateSystemName"), ("vertical_datum", "verticalDatum")):
            if coordinates.get(source): attrs[target] = str(coordinates[source])
        ET.SubElement(root, tag("CoordinateSystem"), attrs)
    ET.SubElement(root, tag("Project"), {"name": str(plan.get("project_name") or "Civora review"), "desc": "Review only; not for construction; external Civil 3D verification required"})
    grading = mapping(meta.get("grading") or {}, "grading")
    surfaces = [(key, grading[key]) for key in ("existing_surface", "proposed_surface") if grading.get(key)]
    if surfaces:
        parent = ET.SubElement(root, tag("Surfaces"))
        for name, grid in surfaces:
            surface_xml(parent, grid, name)
    network_parent = None
    all_ids = set()
    networks = (
        ("storm", "storm", meta.get("storm_pipes") or meta.get("storm_pipe_summary") or {}),
        ("sanitary", "sanitary", meta.get("sanitary") or meta.get("sanitary_summary") or {}),
        ("authored storm", "storm", meta.get("review_pipe_network") or {}),
    )
    for system, pipe_net_type, data in networks:
        data = mapping(data, "network")
        if "exchange_network_v1" in data:
            snapshot = mapping(data["exchange_network_v1"], "exact network snapshot")
            if snapshot.get("geometry_signature") != network_geometry_signature(data):
                raise ValueError("LandXML exact network snapshot is stale; recalculate the changed network before export.")
            data = snapshot
            if data.get("version") != 1:
                raise ValueError("LandXML network snapshot version is unsupported; recalculate first.")
        segments = data.get("segments") or []
        structures = data.get("structures") or data.get("manholes") or []
        if not isinstance(segments, list) or not isinstance(structures, list):
            raise ValueError("LandXML pipe and structure collections must be lists.")
        if not segments and not structures:
            continue
        if not segments or not structures:
            raise ValueError("LandXML network requires connected pipes and structures; no endpoint inference is permitted.")
        if network_parent is None:
            network_parent = ET.SubElement(root, tag("PipeNetworks"), {"name": network_name})
        net = ET.SubElement(network_parent, tag("PipeNetwork"), {
            "name": f"{network_name} {system}",
            "pipeNetType": pipe_net_type,
            "civoraReviewOnly": "true",
            "civoraConstructionReleaseAllowed": "false",
            "civoraCivil3dVerificationStatus": "not_verified",
        })
        structs_node, pipes_node = ET.SubElement(net, tag("Structs")), ET.SubElement(net, tag("Pipes"))
        lookup, records, nodes = {}, {}, {}
        for s in structures:
            s = mapping(s, "structure")
            name = str(pick(s, "name", "id") or "")
            if not name or name in all_ids:
                raise ValueError("LandXML requires unique nonempty pipe and structure names.")
            all_ids.add(name)
            for alias in (name, s.get("id")):
                if alias is not None:
                    if str(alias) in lookup and lookup[str(alias)] != name:
                        raise ValueError("LandXML structure identity is ambiguous.")
                    lookup[str(alias)] = name
            rim = number(pick(s, "rim_elevation_ft", "rim_elev_ft"), "structure rim elevation")
            sump = number(pick(s, "sump_elevation_ft", "invert_elevation_ft", "invert_elev_ft"), "structure sump elevation")
            x, y = number(s.get("x"), "structure x"), number(s.get("y"), "structure y")
            node = ET.SubElement(structs_node, tag("Struct"), {
                "name": name,
                "elevRim": fmt(rim),
                "elevSump": fmt(sump),
                "civoraCanonicalId": str(s.get("canonical_id") or s.get("id") or name),
                "civoraReviewOnly": "true",
            })
            ET.SubElement(node, tag("Center")).text = f"{fmt(y)} {fmt(x)}"
            diameter = pick(s, "diameter_ft", "structure_diameter_ft")
            if diameter is None:
                # Do not invent a catalog part or physical structure size.
                ET.SubElement(node, tag("Connection"))
            else:
                diameter = number(diameter, "structure diameter")
                if diameter <= 0: raise ValueError("LandXML structure diameter must be positive.")
                ET.SubElement(node, tag("CircStruct"), {"diameter": fmt(diameter)})
            records[name], nodes[name] = (x, y, rim, sump), node
        for p in segments:
            p = mapping(p, "pipe")
            name = str(pick(p, "name", "pipe", "id") or "")
            if not name or name in all_ids:
                raise ValueError("LandXML requires unique nonempty pipe and structure names.")
            all_ids.add(name)
            start = lookup.get(str(pick(p, "from_node", "start_name", "upstream_node_name")))
            end = lookup.get(str(pick(p, "to_node", "end_name", "downstream_node_name")))
            if not start or not end or start == end:
                raise ValueError(f"LandXML pipe {name} needs distinct existing start/end structure references.")
            z0 = number(pick(p, "invert_start_ft", "start_invert_ft", "start_invert"), "upstream invert")
            z1 = number(pick(p, "invert_end_ft", "end_invert_ft", "end_invert"), "downstream invert")
            a, b = records[start], records[end]
            geometric_length = math.hypot(b[0]-a[0], b[1]-a[1])
            given = number(p.get("length_ft"), "pipe length")
            if geometric_length <= 0 or not math.isclose(geometric_length, given, rel_tol=1e-5, abs_tol=.01):
                raise ValueError("LandXML supports straight pipes only; pipe length and connected endpoints disagree.")
            # Retain the authored/calculated length after verifying it agrees
            # with endpoint geometry. This preserves the canonical rounded
            # engineering value and keeps its stated slope internally bound.
            length = given
            slope = (z0-z1)/length
            stated = pick(p, "slope_ft_ft", "slope")
            if stated is not None:
                stated_slope = number(stated, "pipe slope")
                if not math.isclose(stated_slope, slope, rel_tol=1e-5, abs_tol=1e-6):
                    raise ValueError("LandXML pipe slope conflicts with its length and invert elevations; recalculate first.")
                slope = stated_slope
            diameter = number(p["diameter_ft"], "pipe diameter") if "diameter_ft" in p else number(p.get("diameter_in"), "pipe diameter")/12
            if diameter <= 0: raise ValueError("LandXML pipe diameter must be positive.")
            path = pick(p, "path", "route_points", "points")
            if path:
                if len(path) != 2: raise ValueError("LandXML bent/curved pipes need explicit segmented topology; export blocked.")
                for point, ref, z in zip(path, (a,b), (z0,z1)):
                    xyz = [point.get(k) for k in ("x","y","z")] if isinstance(point,dict) else list(point)
                    if len(xyz)<2 or any(not math.isclose(number(xyz[i], 'pipe coordinate'),ref[i],abs_tol=.01) for i in (0,1)):
                        raise ValueError("LandXML pipe geometry disagrees with connected structures.")
                    if len(xyz)>2 and xyz[2] is not None and not math.isclose(number(xyz[2], 'pipe elevation'),z,abs_tol=.001):
                        raise ValueError("LandXML pipe path elevation disagrees with invert data.")
            pipe = ET.SubElement(pipes_node, tag("Pipe"), {
                "name": name,
                "refStart": start,
                "refEnd": end,
                "length": fmt(length),
                "slope": fmt(slope*100),
                "civoraCanonicalId": str(p.get("canonical_id") or p.get("id") or name),
                "civoraReviewOnly": "true",
                "civoraConstructionReleaseAllowed": "false",
                "civoraCivil3dVerificationStatus": "not_verified",
            })
            ET.SubElement(pipe, tag("CircPipe"), {"diameter": fmt(diameter)})
            feature(pipe, {"canonical_id": pick(p,"id","canonical_id") or name, "review_only": "true"})
            for ref,z,direction in ((start,z0,"out"),(end,z1,"in")):
                if not records[ref][3] <= z <= records[ref][2]:
                    raise ValueError("LandXML pipe invert lies outside the structure sump/rim range.")
                ET.SubElement(nodes[ref], tag("Invert"), {"refPipe": name, "elev": fmt(z), "flowDir": direction})
        for name,node in nodes.items():
            if node.find(tag("Invert")) is None: raise ValueError("LandXML network contains an unconnected structure.")
            feature(node, {"canonical_id": name, "review_only": "true"})
    if not surfaces and network_parent is None:
        raise ValueError("LandXML needs supported pipe-network data or complete surface nodes.")
    from .export_package_report import build_export_package_report_v1
    audit = ET.SubElement(root, f"{{{AUDIT_NS}}}ExportReport", {"review_only":"true", "construction_release_allowed":"false", "civil3d_status":"not_verified"})
    audit.text = json.dumps(build_export_package_report_v1(plan, export_type="landxml"), sort_keys=True)
    return ET.tostring(root, encoding="unicode")


def verify_exchange(root):
    """Local structural checks, explicitly not an XSD or Civil 3D certification."""
    failures = []
    pipes = root.findall('.//' + tag('Pipe'))
    structs = root.findall('.//' + tag('Struct'))
    surfaces = root.findall('.//' + tag('Surface'))
    report = root.find(f'{{{AUDIT_NS}}}ExportReport')
    units = root.find('./' + tag('Units') + '/' + tag('Imperial'))
    if units is None or any(units.get(k) != v for k,v in {'linearUnit':'foot','diameterUnit':'foot','elevationUnit':'feet'}.items()):
        failures.append('landxml_units_missing_or_unsupported')
    if report is None or report.get('review_only') != 'true' or report.get('construction_release_allowed') != 'false' or report.get('civil3d_status') != 'not_verified':
        failures.append('landxml_review_contract_invalid')
    names = [e.get('name') for e in pipes+structs]
    if any(not n for n in names) or len(set(names)) != len(names): failures.append('landxml_duplicate_or_missing_identity')
    for net in root.findall('.//' + tag('PipeNetwork')):
        nodes = {s.get('name'):s for s in net.findall('./'+tag('Structs')+'/'+tag('Struct'))}
        for p in net.findall('./'+tag('Pipes')+'/'+tag('Pipe')):
            for key,direction in [('refStart','out'),('refEnd','in')]:
                s = nodes.get(p.get(key))
                if s is None or not any(i.get('refPipe')==p.get('name') and i.get('flowDir')==direction for i in s.findall(tag('Invert'))):
                    failures.append('landxml_connectivity_missing')
            circ=p.find(tag('CircPipe'))
            if circ is None or float(circ.get('diameter','0'))<=0: failures.append('landxml_diameter_missing')
    for elem in root.findall('.//'+tag('P')) + root.findall('.//'+tag('Center')):
        try:
            vals=[float(v) for v in (elem.text or '').split()]
            if len(vals) not in (2,3) or not all(math.isfinite(v) for v in vals): raise ValueError()
        except (ValueError,TypeError): failures.append('landxml_coordinate_invalid')
    for inv in root.findall('.//'+tag('Invert')):
        try:
            if not math.isfinite(float(inv.get('elev','nan'))): raise ValueError()
        except (ValueError,TypeError): failures.append('landxml_invert_invalid')
    for s in surfaces:
        points=s.findall('.//'+tag('P')); ids={p.get('id') for p in points}; faces=s.findall('.//'+tag('F'))
        if len(ids)!=len(points) or not points or not faces: failures.append('landxml_surface_incomplete')
        for f in faces:
            refs=(f.text or '').split()
            if len(refs)!=3 or len(set(refs))!=3 or any(r not in ids for r in refs): failures.append('landxml_surface_face_invalid')
    if not pipes and not surfaces: failures.append('landxml_exchange_empty')
    return {'format':'landxml','source':'landxml_exchange_v1','local_parse_status':'passed',
            'roundtrip_parse_status':'passed','schema_like_contract_status':'failed' if failures else 'passed',
            'xsd_validation_status':'not_executed_by_runtime','pipe_count':len(pipes),'structure_count':len(structs),'surface_count':len(surfaces),
            'canonical_id_traceability':{'present':bool(names or surfaces),'canonical_ids':names},
            'export_package_report_present':report is not None,'review_only_flags_ok':report is not None and report.get('review_only')=='true',
            'construction_release_flags_ok':report is not None and report.get('construction_release_allowed')=='false',
            'local_contract_verified':not failures,'externally_verified':False,'civil3d_external_verification_status':'not_verified',
            'landxml_external_verification_status':'not_verified','construction_release_allowed':False,'construction_release_blocked':True,
            'dwg_support_status':'unsupported_no_native_writer','failures':sorted(set(failures)),
            'truth_label':'Structural exchange validation only; actual Civil 3D import and part mapping require external verification.'}
