from __future__ import annotations

from typing import Any, Dict

from backend.planning.customer_templates import GLOBAL_CUSTOMER_TEMPLATE_MANAGER


def customer_template_registry_response() -> Dict[str, Any]:
    return GLOBAL_CUSTOMER_TEMPLATE_MANAGER.snapshot()


def import_customer_template_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return GLOBAL_CUSTOMER_TEMPLATE_MANAGER.import_template(dict(payload or {}))


def activate_customer_template_response(template_id: str = "") -> Dict[str, Any]:
    return GLOBAL_CUSTOMER_TEMPLATE_MANAGER.activate(template_id)


def export_customer_templates_response() -> Dict[str, Any]:
    return GLOBAL_CUSTOMER_TEMPLATE_MANAGER.export_json()


def explain_missing_customer_template_response(template_id: str = "") -> Dict[str, Any]:
    return GLOBAL_CUSTOMER_TEMPLATE_MANAGER.explain_missing(template_id)
