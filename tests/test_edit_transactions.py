from copy import deepcopy
import pytest
from backend.services.edit_transactions import editable_input, seal_edit_history, validate_ledger, KEY
from backend.services.canonical_project import ProjectDocumentError

def inputs(x=100):
    return {"manual_fields": {"units": "ft", "site_objects": [{"id": "a", "type": "building", "x": x, "y": 0, "w": 20, "d": 20}]}}

def saved(value, previous=None):
    result=deepcopy(value)
    result.setdefault("meta", {})[KEY]=seal_edit_history(value, previous or {}, "actual-user")
    return result

def test_server_writers_adopt_and_record_revisions_and_preserve_actor():
    first=saved(inputs()); second=saved(inputs(120),first)
    tx=second["meta"][KEY]["transactions"][0]
    assert tx["before"]==editable_input(first)
    assert tx["after"]==editable_input(second)
    assert tx["actor"]=={"kind":"user","user_id":"actual-user"}
    assert tx["affected_object_ids"]==["a"]
    assert saved(second,second)["meta"][KEY]==second["meta"][KEY]

def test_undo_redo_and_abandoned_branch_survive_serialization():
    first=saved(inputs()); second=saved(inputs(120),first)
    undo=inputs();undo["meta"]={KEY:deepcopy(second["meta"][KEY])}
    ledger=undo["meta"][KEY];old=ledger["head"];ledger["head"]=None;ledger["redo"]=[old]
    undone=saved(undo,second);assert undone["meta"][KEY]["head"] is None
    branched=saved(inputs(140),undone)
    assert len(branched["meta"][KEY]["transactions"])==2
    assert branched["meta"][KEY]["transactions"][0]["id"]==old
    assert branched["meta"][KEY]["redo"]==[]


def test_both_legacy_merge_boundaries_treat_branch_cursor_as_atomic():
    from backend.services.project_store import _merge_project_input as store_merge
    from backend.application.project_workflows import _merge_project_input as workflow_merge
    first = saved(inputs())
    second = saved(inputs(120), first)
    undo = inputs()
    undo["meta"] = {KEY: deepcopy(second["meta"][KEY])}
    old = undo["meta"][KEY]["head"]
    undo["meta"][KEY].update(head=None, redo=[old])
    undone = saved(undo, second)
    branched = saved(inputs(140), undone)
    for merge in (store_merge, workflow_merge):
        merged = merge(undone, branched)
        assert validate_ledger(merged["meta"][KEY])["redo"] == []
        assert merged["meta"][KEY]["head"] == branched["meta"][KEY]["head"]
        assert len(merged["meta"][KEY]["transactions"]) == 2

@pytest.mark.parametrize("mutation",["rewrite","parent","head","redo","objects"])
def test_corrupt_or_rewritten_history_cannot_be_saved(mutation):
    first=saved(inputs());second=saved(inputs(120),first);bad=deepcopy(second);ledger=bad["meta"][KEY]
    if mutation=="erase":ledger["transactions"]=[];ledger["head"]=None
    elif mutation=="rewrite":ledger["transactions"][0]["reason"]="Altered"
    elif mutation=="parent":ledger["transactions"][0]["parent_id"]=ledger["head"]
    elif mutation=="head":ledger["head"]="missing"
    elif mutation=="redo":ledger["redo"]=[ledger["head"]]
    else:ledger["transactions"][0]["after"]["manual_fields"]["site_objects"]*=2
    with pytest.raises(ProjectDocumentError):seal_edit_history(bad,second,"actual-user")

def test_forged_actor_is_replaced_and_old_actor_cannot_be_rewritten():
    first=saved(inputs()); second=saved(inputs(120),first)
    second["meta"][KEY]["transactions"][0]["actor"]["user_id"]="forged"
    result=seal_edit_history(second,first,"real-editor")
    assert result["transactions"][0]["actor"]["user_id"]=="real-editor"
    previous=deepcopy(second);previous["meta"][KEY]=result
    assert seal_edit_history(second,previous,"other-editor")["transactions"][0]["actor"]["user_id"]=="real-editor"

def test_stale_prefix_cannot_erase_newer_server_transactions():
    first=saved(inputs());second=saved(inputs(120),first)
    incoming=deepcopy(second);incoming["meta"][KEY]=deepcopy(first["meta"][KEY])
    assert seal_edit_history(incoming,second,"actual-user")==second["meta"][KEY]

def test_restore_defaults_are_not_new_edits_and_do_not_clear_redo():
    first=saved(inputs());second=saved(inputs(120),first)
    undo=deepcopy(first);ledger=deepcopy(second["meta"][KEY]);ledger["redo"]=[ledger["head"]];ledger["head"]=None
    undo["meta"][KEY]=ledger
    undo["manual_fields"]["site_objects"][0].update(locked=False,generated=False,systemDependencies=["roads","parking","grading","drainage","utilities"])
    result=seal_edit_history(undo,second,"actual-user")
    assert result["head"] is None
    assert result["redo"]==ledger["redo"]

def test_locked_project_boundary_invalidates_existing_results_without_deleting_them():
    from backend.services.canonical_record import seal_record
    from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input
    first=inputs();first["meta"]={"system_dirty_state":{"roads":"fresh","parking":"not_generated"}}
    previous=seal_record({"project_id":"pilot","project_input":with_canvas_snapshot(first),"latest_result":{"evidence":"retained"}})
    changed=inputs(120);changed["meta"]={"system_dirty_state":{"roads":"fresh","parking":"not_generated"}}
    result=seal_record({**previous,"project_input":with_canvas_snapshot(changed)},previous=previous,latest_result_supplied=False,actor_user_id="editor")
    statuses=resolve_canvas_input(result["project_input"])["meta"]["system_dirty_state"]
    assert statuses=={"roads":"stale","parking":"not_generated"}
    assert result["latest_result"]==previous["latest_result"]

def test_approved_divergent_branch_preserves_both_histories_and_accepts_following_edits():
    first=saved(inputs());one=saved(inputs(120),first);two=saved(inputs(140),first)
    merged=seal_edit_history(one,two,"editor")
    assert {tx["id"] for tx in merged["transactions"]}=={one["meta"][KEY]["head"],two["meta"][KEY]["head"]}
    assert merged["head"]==one["meta"][KEY]["head"]
    prior=deepcopy(one);prior["meta"][KEY]=merged
    incoming=inputs(160);incoming["meta"]={KEY:deepcopy(one["meta"][KEY])}
    following=seal_edit_history(incoming,prior,"editor")
    assert len(following["transactions"])==3
    assert following["transactions"][-1]["after"]["manual_fields"]["site_objects"][0]["x"]==160
