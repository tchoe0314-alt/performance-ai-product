import unittest

from engines.error_check_engine import run_plan_checks


class ActionContractTest(unittest.TestCase):
    def test_point_actions_are_supported_by_qa(self) -> None:
        plan = {
            "project_name": "Point Contract",
            "units": "ft",
            "actions": [
                {"task": "point", "origin": [10.0, 20.0], "label": "LP-1", "layer": "LOW_POINTS"},
                {"task": "text_note", "origin": [10.0, 20.0], "text": "LOW", "layer": "ANNO"},
            ],
            "meta": {},
        }
        issues = run_plan_checks({"mode": "site_plan", "lot": {"w": 100.0, "h": 100.0}}, plan) or []
        messages = [str(item.get("message") or "").lower() for item in issues if isinstance(item, dict)]
        self.assertFalse(any("unknown task 'point'" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
