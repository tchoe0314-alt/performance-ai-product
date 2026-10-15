"""Account-owned reusable classifications; no inferred engineering rules."""
import json
import re


def validate_custom_type(value):
    if not isinstance(value, dict) or value.get("version") != 1 or type(value.get("version")) is not int:
        raise ValueError("Unsupported custom type version.")
    if not isinstance(value.get("id"), str) or not re.fullmatch(r"custom-[a-zA-Z0-9-]{1,100}", value["id"]):
        raise ValueError("Custom types need a stable ID.")
    if not isinstance(value.get("name"), str) or not 1 <= len(value["name"].strip()) <= 100:
        raise ValueError("Type name must be 1–100 characters.")
    fields = value.get("fields")
    if not isinstance(fields, list) or len(fields) > 30:
        raise ValueError("Custom types support up to 30 fields.")
    names = set()
    clean = []
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not 1 <= len(field["name"].strip()) <= 80 or field.get("type") not in ("text", "number", "boolean"):
            raise ValueError("Use named text, number or checkbox fields.")
        name = field["name"].strip()
        if name.lower() in names or name in ("__proto__", "prototype", "constructor"):
            raise ValueError("Field names must be unique.")
        names.add(name.lower())
        entry = {"name": name, "type": field["type"]}
        if "unit" in field:
            if not isinstance(field["unit"], str) or len(field["unit"]) > 30:
                raise ValueError("Field units must be short text.")
            entry["unit"] = field["unit"].strip()
        clean.append(entry)
    return {"version": 1, "id": value["id"], "name": value["name"].strip(), "fields": clean}


class ObjectTypeStore:
    def __init__(self, db):
        self.db = db

    def list_types(self, user_id):
        connection = self.db.connect()
        try:
            return [json.loads(row["definition_json"]) for row in connection.execute("SELECT definition_json FROM user_object_types WHERE user_id = ? ORDER BY type_id", (user_id,)).fetchall()]
        finally:
            connection.close()

    def save_type(self, user_id, value):
        definition = validate_custom_type(value)
        connection = self.db.connect()
        try:
            connection.execute("INSERT INTO user_object_types(user_id, type_id, definition_json) VALUES (?, ?, ?) ON CONFLICT (user_id, type_id) DO UPDATE SET definition_json = excluded.definition_json", (user_id, definition["id"], json.dumps(definition, allow_nan=False)))
            connection.commit()
        finally:
            connection.close()
        return definition
