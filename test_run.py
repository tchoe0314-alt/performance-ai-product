# test_run.py

from geometry.layout_engine import generate_smart_layout
from core.constraint_engine import validate_site_layout
from engines.autofix_engine import autofix_site_layout
from output.preview import preview_plan
from output.dxf_exporter import save_dxf


def layout_to_actions(layout):
    return [
        {
            "task": "rectangle",
            "origin": (layout["lot"]["x"], layout["lot"]["y"]),
            "width": layout["lot"]["w"],
            "height": layout["lot"]["h"],
            "label": "LOT",
            "layer": "SITE",
        },
        {
            "task": "rectangle",
            "origin": (layout["building"]["x"], layout["building"]["y"]),
            "width": layout["building"]["w"],
            "height": layout["building"]["h"],
            "label": "BLDG",
            "layer": "BUILDING",
        },
        {
            "task": "rectangle",
            "origin": (layout["parking"]["x"], layout["parking"]["y"]),
            "width": layout["parking"]["w"],
            "height": layout["parking"]["h"],
            "label": "PARK",
            "layer": "PAVEMENT",
        },
        {
            "task": "rectangle",
            "origin": (layout["driveway"]["x"], layout["driveway"]["y"]),
            "width": layout["driveway"]["w"],
            "height": layout["driveway"]["h"],
            "label": "DRIVE",
            "layer": "ROAD",
        },
    ]


def main():
    lot = {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0}
    setback = 10.0

    print("\n--- GENERATING SMART LAYOUT ---")
    layout = generate_smart_layout(
        lot=lot,
        setback=setback,
        layout_strategy="front_parking",
    )
    print(layout)

    print("\n--- VALIDATING LAYOUT ---")
    issues = validate_site_layout(layout)
    if issues:
        for issue in issues:
            print(f"{issue.severity.upper()} | {issue.code} | {issue.message}")
    else:
        print("No layout issues found.")

    print("\n--- APPLYING AUTOFIX IF NEEDED ---")
    fixed_layout = autofix_site_layout(layout, issues)
    print(fixed_layout)

    print("\n--- RE-VALIDATING FIXED LAYOUT ---")
    fixed_issues = validate_site_layout(fixed_layout)
    if fixed_issues:
        for issue in fixed_issues:
            print(f"{issue.severity.upper()} | {issue.code} | {issue.message}")
    else:
        print("No layout issues found after autofix.")

    plan = {
        "project_name": "Smart Layout Test",
        "units": "ft",
        "actions": layout_to_actions(fixed_layout),
        "meta": {"layout": fixed_layout},
    }

    print("\n--- OPENING PREVIEW ---")
    preview_plan(plan)

    print("\n--- SAVING DXF ---")
    filename = save_dxf(plan)
    print(f"DXF saved as: {filename}")


if __name__ == "__main__":
    main()