import unittest

from backend.planning.execution_control import mark_stage_skipped_clean
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision


class _DummyManager:
    def __init__(self) -> None:
        self.system_dirty_state = {}


class ExecutionControlTest(unittest.TestCase):
    def test_skipped_clean_preserves_completed_resumed_stage(self):
        ctx = PlannerExecutionContext(
            parsed={},
            manager=_DummyManager(),
            route=RoutingDecision(path="test", reasons=[]),
        )
        ctx.add_stage(
            "layout",
            True,
            "Restored layout state from saved checkpoint.",
            resumed_from_checkpoint=True,
            completeness="complete",
        )

        mark_stage_skipped_clean(ctx, "layout")

        latest = ctx.stage_results[-1]
        self.assertEqual(latest.stage_name, "layout")
        self.assertEqual(latest.meta.get("completeness"), "complete")


if __name__ == "__main__":
    unittest.main()
