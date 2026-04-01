from backend.planning.orchestrator import orchestrate_prompt

result = orchestrate_prompt(
    "Create a commercial pad site on a 140 by 110 foot lot with front parking and 24 spaces",
    strict_mode=False,
    full_design_mode=False,
    plan_type_hint="commercial_pad",
    units="ft",
)

print("=== RESULT ===")
print("success:", result.success)
print("message:", result.message)
print("actions:", len(result.final_plan.get("actions", [])))
print("warnings:", result.warnings)
print("errors:", result.errors)
print("metadata:", result.metadata)
print("qa:", result.final_plan.get("meta", {}).get("qa"))
print("quantities:", result.final_plan.get("meta", {}).get("quantities"))
