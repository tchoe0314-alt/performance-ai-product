"""User-owned view preferences, deliberately separate from project records."""
import json

DEFAULT_LAYOUT = {"version": 1, "mode": "simple", "leftWidth": 260, "rightWidth": 320,
                  "deltaHeight": 64, "leftVisible": False, "rightVisible": False, "deltaVisible": False}

def validate_layout(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_LAYOUT) or type(value["version"]) is not int or value["version"] != 1 or value["mode"] not in {"simple", "professional"}:
        raise ValueError("Unsupported workspace layout.")
    for key, low, high in [("leftWidth", 220, 440), ("rightWidth", 280, 480), ("deltaHeight", 48, 160)]:
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("Invalid panel size.")
    for key in ("leftVisible", "rightVisible", "deltaVisible"):
        if type(value[key]) is not bool:
            raise ValueError("Invalid panel visibility.")
    return dict(value)

def read_layout(db, user_id):
    connection = db.connect()
    try:
        row = connection.execute("SELECT layout_json FROM user_workspace_layouts WHERE user_id = ?", (user_id,)).fetchone()
        try:
            return validate_layout(json.loads(row["layout_json"])) if row else dict(DEFAULT_LAYOUT)
        except (ValueError, TypeError, KeyError):
            return dict(DEFAULT_LAYOUT)
    finally:
        connection.close()

def save_layout(db, user_id, value):
    value = validate_layout(value)
    connection = db.connect()
    try:
        connection.execute("INSERT INTO user_workspace_layouts (user_id, layout_json) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET layout_json = excluded.layout_json", (user_id, json.dumps(value)))
        connection.commit()
    finally:
        connection.close()
    return value
