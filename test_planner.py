from backend.planning.planner import build_plan

demo = {
    "project_name": "Planner Smoke Test",
    "units": "ft",
    "mode": "site_plan",
    "project_type": "commercial_pad",
    "site_type": "commercial_pad",
    "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
    "setback": 10.0,
    "street_edge": "bottom",
    "layout_strategy": "front_parking",
    "site_plan": {
        "building_width": 48.0,
        "building_depth": 34.0,
        "parking_count": 24
    }
}

out = build_plan(demo)

print("=== RESULT ===")
print("project:", out.get("project_name"))
print("actions:", len(out.get("actions", [])))

meta = out.get("meta", {})
print("planner score:", meta.get("planner_score"))
print("qa:", meta.get("qa"))

q = meta.get("quantities")
print("quantities:", q)
