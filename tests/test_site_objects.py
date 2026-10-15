import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from backend.services.auth_store import AuthStore

from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input, seal_canvas_objects
from backend.services.canonical_project import ProjectDocumentError
from backend.services.site_objects import TYPES, object_definition, calculation_blockers, validate_group_graph
from backend.services.object_type_store import ObjectTypeStore, validate_custom_type
from backend.services.database import Database
from backend.application.design_workflows import _canonical_calculation_payload
from fastapi import HTTPException


class SiteObjectTests(unittest.TestCase):
    def object(self, **updates):
        return {"id":"a", "label":"Outline", "type":"building", "x":0,"y":0,"w":20,"d":20, "geometry_type":"polygon", "geometry":[[0,0],[20,0],[20,20],[0,20]], **updates}

    def test_every_catalog_type_has_complete_stable_contract(self):
        for kind, definition in TYPES.items():
            with self.subTest(kind=kind):
                geometry = definition["geometry"][0]
                item = self.object(type=kind, geometry_type=geometry)
                if geometry == "point": item["geometry"] = [[0,0]]
                record = object_definition(item,"ft")
                self.assertEqual(record["schema_version"], "civora_object_v1")
                self.assertEqual(record["revision"]["number"],1)
                self.assertFalse(record["validation"]["engineering_verified"])
                self.assertEqual(record["layer"]["id"],definition["layer"])

    def test_native_geometry_beats_shadow_and_revisions_only_change_on_edit(self):
        compiled = with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[self.object(height_ft=40)]}})
        record = compiled["canonical_project_v1"]["buildings"][0]["object_v1"]
        self.assertEqual(record["geometry"]["size"][2],40)
        record["geometry"]["origin"][0] = 33
        resolved = resolve_canvas_input(compiled)
        self.assertEqual(resolved["manual_fields"]["site_objects"][0]["x"],33)
        previous = with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[self.object(height_ft=40)]}})["canonical_project_v1"]
        sealed = seal_canvas_objects(deepcopy(compiled["canonical_project_v1"]),previous)
        self.assertEqual(sealed["buildings"][0]["object_v1"]["revision"]["number"],2)
        self.assertEqual(seal_canvas_objects(deepcopy(sealed),sealed)["buildings"][0]["object_v1"]["revision"]["number"],2)

    def test_open_building_saves_but_calculation_is_paused(self):
        item=self.object(geometry_type="polyline",geometry=[[0,0],[20,0],[20,20]])
        compiled=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[item]}})
        self.assertEqual(resolve_canvas_input(compiled)["manual_fields"]["site_objects"],[item])
        self.assertEqual(object_definition(item,"ft")["validation"]["status"],"invalid")
        with self.assertRaises(HTTPException) as error: _canonical_calculation_payload(compiled)
        self.assertEqual(error.exception.status_code,422)
        self.assertEqual(error.exception.detail["objects"][0]["object_id"],"a")
        item["geometry_type"]="polygon"
        self.assertEqual(calculation_blockers([item]),[])

    def test_custom_and_organizational_geometry_never_invents_engineering_rules(self):
        custom=self.object(type="custom",geometry_type="polyline",geometry=[[0,0],[20,0]])
        record=object_definition(custom,"ft")
        self.assertEqual(record["validation"]["status"],"unverified")
        self.assertEqual(calculation_blockers([custom]),[])
        self.assertEqual(object_definition(self.object(type="group",geometry_type="rect"),"ft")["export_mapping"]["mode"],"organization_only")

    def test_geometry_self_crossing_zero_edges_and_duplicates(self):
        for geometry in ([[0,0],[20,20],[0,20],[20,0]], [[0,0],[20,0],[20,0],[0,20]]):
            self.assertTrue(calculation_blockers([self.object(geometry=geometry)]))
        with self.assertRaises(ProjectDocumentError): validate_group_graph([self.object(),self.object()])

    def test_nested_groups_reject_missing_parent_cycles_and_non_group_parent(self):
        outer=self.object(id="outer",type="group",geometry_type="rect")
        inner=self.object(id="inner",type="group",geometry_type="rect",meta={"group_id":"outer"})
        child=self.object(meta={"group_id":"inner"})
        validate_group_graph([outer,inner,child])
        for parent in ("missing","a","inner"):
            outer["meta"]={"group_id":parent}
            with self.assertRaises(ProjectDocumentError): validate_group_graph([outer,inner,child])

    def test_calculation_scope_ignores_unrelated_invalid_object(self):
        basin=self.object(type="basin",geometry_type="polyline")
        self.assertEqual(calculation_blockers([basin],["parking"]),[])
        self.assertTrue(calculation_blockers([basin],["drainage"]))

    def test_creator_attribution_uses_authenticated_actor_and_does_not_rewrite_history(self):
        item=self.object(source="manual_drawn")
        document=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[item]}})["canonical_project_v1"]
        document["buildings"][0]["object_v1"]["created_by"]["actor_id"]="client-claim"
        sealed=seal_canvas_objects(document,actor_user_id="authenticated-owner")
        self.assertEqual(sealed["buildings"][0]["object_v1"]["created_by"]["actor_id"],"authenticated-owner")
        later=seal_canvas_objects(deepcopy(sealed),sealed,actor_user_id="other-editor")
        self.assertEqual(later["buildings"][0]["object_v1"]["created_by"]["actor_id"],"authenticated-owner")
        legacy=seal_canvas_objects(deepcopy(document),actor_user_id="migration-editor",prior_object_ids={"a"})
        self.assertIsNone(legacy["buildings"][0]["object_v1"]["created_by"]["actor_id"])

    def test_custom_library_validation(self):
        definition={"version":1,"id":"custom-test","name":"Pipe marker","fields":[{"name":"Diameter","type":"number","unit":"in"}]}
        self.assertEqual(validate_custom_type(definition),definition)
        for extra in ({"name":"diameter","type":"text"},{"name":"__proto__","type":"text"}):
            with self.assertRaises(ValueError): validate_custom_type({**definition,"fields":definition["fields"]+[extra]})

    def test_account_library_is_private_persistent_and_removed_with_account(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Database(Path(directory)/"objects.db")
            auth=AuthStore(db)
            owner=auth.register_user(email="owner@example.test",password="Disposable-object-123",name="Owner")["user"]["user_id"]
            other=auth.register_user(email="other@example.test",password="Disposable-object-123",name="Other")["user"]["user_id"]
            definition={"version":1,"id":"custom-pipe","name":"Pipe marker","fields":[]}
            ObjectTypeStore(db).save_type(owner,definition)
            self.assertEqual(ObjectTypeStore(Database(Path(directory)/"objects.db")).list_types(owner),[definition])
            self.assertEqual(ObjectTypeStore(db).list_types(other),[])
            connection=db.connect()
            connection.execute("DELETE FROM users WHERE user_id = ?",(owner,))
            connection.commit();connection.close()
            self.assertEqual(ObjectTypeStore(db).list_types(owner),[])


if __name__ == "__main__": unittest.main()
