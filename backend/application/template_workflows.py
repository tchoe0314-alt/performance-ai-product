from __future__ import annotations

from typing import Any, Dict


def customer_template_registry_response(*, library) -> Dict[str, Any]:
    return library("templates", "snapshot")


def import_customer_template_response(payload: Dict[str, Any], *, library) -> Dict[str, Any]:
    return library("templates", "import_template", dict(payload or {}))


def activate_customer_template_response(template_id: str = "", *, library) -> Dict[str, Any]:
    return library("templates", "activate", template_id=template_id)


def export_customer_templates_response(*, library) -> Dict[str, Any]:
    return library("templates", "export_json")


def explain_missing_customer_template_response(template_id: str = "", *, library) -> Dict[str, Any]:
    return library("templates", "explain_missing", template_id=template_id)
