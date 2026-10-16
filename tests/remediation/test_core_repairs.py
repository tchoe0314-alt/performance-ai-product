"""Independent analytical/security regressions. Synthetic temporary data only.

No app startup, network or existing project data. Standard unittest avoids root
pytest startup fixtures. New DBs use an explicit non-Postgres override.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr
import hashlib
import io
import json
import math
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from p01_evidence import extracted
from fastapi import HTTPException


_network_guard_active = False


def _no_network(event,args):
    if _network_guard_active and event in {"socket.connect","socket.connect_ex","socket.getaddrinfo","socket.bind"}:
        raise PermissionError("Offline repair tests forbid network access")
sys.addaudithook(_no_network)


class OfflineTestCase(unittest.TestCase):
    def run(self, result=None):
        global _network_guard_active
        previous = _network_guard_active
        _network_guard_active = True
        try:
            return super().run(result)
        finally:
            _network_guard_active = previous


class HydrologyTests(OfflineTestCase):
    def test_invalid_inputs(self):
        from engines.hydrology_engine import RationalArea,compute_rational_method,EngineeringInputError
        for index in range(3):
            for bad in (None,True,"2",float("nan"),float("inf"),-1):
                values=[2,.8,4];values[index]=bad
                with self.subTest(index=index,bad=repr(bad)),self.assertRaises(EngineeringInputError):
                    compute_rational_method([RationalArea("synthetic",*values)])
    def test_zero_and_empty_are_distinct(self):
        from engines.hydrology_engine import RationalArea,compute_rational_method
        empty=compute_rational_method([]);zero=compute_rational_method([RationalArea("synthetic",0,.8,4)])
        self.assertFalse(empty.success);self.assertEqual(empty.status,"no_catchments")
        self.assertTrue(zero.success);self.assertEqual(zero.total_runoff_cfs,0)
    def test_composite_arithmetic_and_overflow(self):
        from engines.hydrology_engine import RationalArea,compute_rational_method,EngineeringComputationError
        result=compute_rational_method([RationalArea("a",1,.5,4),RationalArea("b",2,.8,3)])
        self.assertAlmostEqual(result.total_runoff_cfs,1.008*(2+4.8),places=10)
        with self.assertRaises(EngineeringComputationError):compute_rational_method([RationalArea("huge",1e308,1,1e308)])
    def test_adapter_does_not_fabricate_missing_result(self):
        ns={"PIPE_INTENSITY_IN_HR":4,"RationalArea":lambda **kwargs:kwargs,"compute_rational_method":lambda _:SimpleNamespace(success=True)}
        extracted("backend/planning/common.py",["safe_float","safe_dict","clamp","rect_area"],ns)
        extracted("backend/planning/runtime.py",["_lot_area","_compute_hydrology_metrics"],ns)
        with self.assertRaisesRegex(ValueError,"missing total_runoff_cfs"):
            ns["_compute_hydrology_metrics"]({"lot":{"w":100,"h":100}}, {})


class DetentionTests(OfflineTestCase):
    def test_simpson_independent_integral_oracle(self):
        from engines.detention_engine import BasinGeometry,basin_storage_cf,generate_stage_storage_curve
        for length,width,depth,slope in ((100,20,5,4),(100,100,5,4),(7,3,1.37,2),(20,30,2,0),(100,20,5.01,4)):
            area=lambda z:(length+2*slope*z)*(width+2*slope*z)
            expected=depth/6*(area(0)+4*area(depth/2)+area(depth))
            curve=generate_stage_storage_curve(BasinGeometry(length,width,depth,slope))
            self.assertAlmostEqual(basin_storage_cf(length,width,depth,slope),expected,places=7)
            self.assertAlmostEqual(curve[-1].storage_cf,expected,places=7)
            self.assertTrue(all(b.storage_cf>=a.storage_cf for a,b in zip(curve,curve[1:])))
    def test_invalid_geometry_and_curve_inputs(self):
        from engines.detention_engine import basin_storage_cf,BasinGeometry,generate_stage_storage_curve
        for value in (-1,True,None,float("inf"),float("nan")):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):basin_storage_cf(100,20,value,4)
        with self.assertRaises(ValueError):generate_stage_storage_curve(BasinGeometry(100,20,5,4),stage_increment_ft=0)
    def test_zero_outlet_conserves_every_interval(self):
        from engines.detention_engine import BasinGeometry,generate_stage_storage_curve,route_detention_level_pool
        curve=generate_stage_storage_curve(BasinGeometry(100,100,5,4))
        rows=route_detention_level_pool([(0,0),(1,.1),(2,0)],curve,outlet_area_sf=0)
        self.assertAlmostEqual(rows[-1].storage_cf,360,places=7)
        for a,b in zip(rows,rows[1:]):
            self.assertAlmostEqual(a.storage_cf+b.interval_inflow_volume_cf-b.interval_outflow_volume_cf,b.storage_cf,places=7)
            self.assertAlmostEqual(b.continuity_residual_cf,0,places=7)
    def test_out_of_range_original_fixture_rejected(self):
        from engines.detention_engine import BasinGeometry,generate_stage_storage_curve,route_detention_level_pool
        curve=generate_stage_storage_curve(BasinGeometry(40,20,3,3))
        with self.assertRaisesRegex(ValueError,"storage|overflow"):
            route_detention_level_pool([(0,0),(.5,10),(1,0),(2,0)],curve,outlet_area_sf=.5)
    def test_invalid_time_and_curve(self):
        from engines.detention_engine import BasinGeometry,generate_stage_storage_curve,route_detention_level_pool
        curve=generate_stage_storage_curve(BasinGeometry(100,100,5,4))
        for hydro in ([(1,0),(0,1)],[(0,0),(0,1)],[(0,0),(1,-1)],[(0,0),(1,float("nan"))]):
            with self.subTest(hydro=repr(hydro)),self.assertRaises(ValueError):route_detention_level_pool(hydro,curve)
        with self.assertRaisesRegex(ValueError,"timestep budget"):
            route_detention_level_pool([(0,0),(1e308,0)],curve)
        with self.assertRaisesRegex(ValueError,"sample count"):
            generate_stage_storage_curve(BasinGeometry(100,100,5,4),stage_increment_ft=1e-320)


class SurfaceTests(OfflineTestCase):
    def pair(self,values=None,*,sampling="nodes",shift=0):
        from engines.surface_engine import GridSurface
        values=values or [[101.]*3 for _ in range(3)]
        n=len(values);size=20/(n-1 if sampling=="nodes" else n)
        return GridSurface(0,0,20,20,size,n,n,[[100.]*n for _ in range(n)],sampling=sampling),GridSurface(shift,0,shift+20,20,size,n,n,values,sampling=sampling)
    def test_uniform_volume_all_paths(self):
        from engines.surface_integration import cut_fill
        from engines.surface_engine import compare_surfaces
        from engines.grading_engine import GradingEngine
        from engines.earthwork_engine import compute_earthwork
        for n in (2,3,5,11):
            a,b=self.pair([[101.]*n for _ in range(n)])
            self.assertAlmostEqual(cut_fill(a,b)[1],400,places=7)
            self.assertAlmostEqual(compare_surfaces(a,b)["fill_cf"],400,places=7)
            self.assertAlmostEqual(GradingEngine(a)._compute_earthwork(b)[1],400,places=7)
            self.assertAlmostEqual(compute_earthwork(a,b)["results"]["fill_cf"],400,places=7)
    def test_plane_and_zero_crossing_conservation(self):
        from engines.surface_integration import cut_fill
        for values,expected in (([[100,100.5,101]]*3,(0,200,200)),([[99,100,101]]*3,(100,100,0))):
            actual=cut_fill(*self.pair(values))
            for x,y in zip(actual,expected):self.assertAlmostEqual(x,y,places=7)
    def test_explicit_cells_keep_distinct_semantics(self):
        from engines.surface_integration import cut_fill
        self.assertEqual(cut_fill(*self.pair([[101]*2]*2,sampling="cells")),(0,400,400))
    def test_ambiguous_and_nodata_fail_without_mutation(self):
        from engines.surface_integration import cut_fill
        a,b=self.pair();b.ncols=b.nrows=2;b.values=[[101,101],[101,101]]
        with self.assertRaisesRegex(ValueError,"bounds"):cut_fill(a,b)
        self.assertEqual(b.values,[[101,101],[101,101]])
        a,b=self.pair();b.values[0][0]=None
        with self.assertRaisesRegex(ValueError,"NoData"):cut_fill(a,b)
    def test_registration_mismatch_and_unsupported_boundary_fail(self):
        from engines.surface_integration import cut_fill
        for key in ("horizontal_crs","horizontal_units","vertical_units","vertical_datum","axis_order"):
            a,b=self.pair();b.registration[key]="different"
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,key):cut_fill(a,b)
        a,b=self.pair();a.registration["boundary"]=[[0,0],[10,0],[0,10]]
        with self.assertRaisesRegex(ValueError,"Boundary"):cut_fill(a,b)
    def test_all_entrypoints_reject_displacement(self):
        from engines.surface_engine import compare_surfaces
        from engines.grading_engine import GradingEngine
        from engines.earthwork_engine import compute_earthwork,validate_compatible_surfaces
        a,b=self.pair(shift=1000)
        self.assertFalse(compute_earthwork(a,b)["success"])
        self.assertFalse(validate_compatible_surfaces(a,b)["success"])
        with self.assertRaises(ValueError):compare_surfaces(a,b)
        with self.assertRaises(ValueError):GradingEngine(a)._compute_earthwork(b)
    def test_stripping_and_factors_separate_from_raw_volume(self):
        from engines.earthwork_engine import compute_earthwork
        a,b=self.pair()
        result=compute_earthwork(a,b,strip_depth_ft=.5,shrink_factor=1.1,swell_factor=1.2)
        self.assertAlmostEqual(result["results"]["fill_cf"],600)
        self.assertAlmostEqual(result["results"]["stripped_volume_cf"],200)
        self.assertAlmostEqual(result["results"]["adjusted_fill_required_cf"],660)


class EgressTests(OfflineTestCase):
    def resolve(self,*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34",443))]
    def test_private_and_unsafe_urls(self):
        from backend.services.outbound_http import validate_destination
        for url in ("https://127.0.0.1/","https://[::1]/","https://169.254.169.254/","https://10.0.0.1/","http://example.com/","https://user:pass@example.com/","https://localhost/","https://example.com:8080/"):
            with self.subTest(url=url),self.assertRaises(ValueError):validate_destination(url,resolver=self.resolve)
    def test_mixed_dns_and_rebinding_pin(self):
        from backend.services.outbound_http import validate_destination,safe_get
        with self.assertRaises(ValueError):validate_destination("https://example.com",resolver=lambda *a,**k:[(2,1,6,"",("127.0.0.1",443))])
        recorded=[]
        class Connection:
            def __init__(self,*a,**k):self.sock=None
            def request(self,*a,**k):self._create_connection(("example.com",443),1)
            def close(self):pass
            def getresponse(self):
                stream=io.BytesIO(b'{"ok":true}')
                return SimpleNamespace(status=200,getheader=lambda name,default=None:default,getheaders=lambda:[],read1=stream.read)
        with patch("backend.services.outbound_http.http.client.HTTPSConnection",Connection),patch("backend.services.outbound_http.socket.create_connection",side_effect=lambda addr,*a:recorded.append(addr)):
            result=safe_get("https://example.com",resolver=self.resolve)
        self.assertEqual(recorded,[("93.184.216.34",443)]);self.assertTrue(result.json()["ok"])
    def test_redirect_revalidated_and_response_bounded(self):
        from backend.services.outbound_http import safe_get,MAX_BYTES
        class Redirect:
            def __init__(self,*a,**k):pass
            def request(self,*a,**k):pass
            def close(self):pass
            def getresponse(self):return SimpleNamespace(status=302,getheader=lambda name:"https://127.0.0.1/private")
        with patch("backend.services.outbound_http.http.client.HTTPSConnection",Redirect),self.assertRaises(ValueError):safe_get("https://example.com",resolver=self.resolve)
        fake=SimpleNamespace(get=lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{"x":"a"*MAX_BYTES}))
        with self.assertRaisesRegex(ValueError,"large"):safe_get("https://example.com",resolver=self.resolve,session=fake)


class StorageSecurityTests(OfflineTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="civora-core-repairs-");self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def helpers(self):
        return extracted("backend/application/file_workflows.py",["_copy_upload_with_limit","_source_sha256"],
                         {"Path":Path,"os":os,"tempfile":tempfile,"hashlib":hashlib,"HTTPException":HTTPException,"_format_bytes":str})
    def test_upload_collision_and_oversize_preserve_original(self):
        helpers=self.helpers();target=self.root/"source.png";target.write_bytes(b"original")
        for contents,limit in ((b"new",100),(b"too large",1)):
            with self.assertRaises(HTTPException):helpers["_copy_upload_with_limit"](file=SimpleNamespace(file=io.BytesIO(contents)),target=target,max_bytes=limit)
            self.assertEqual(target.read_bytes(),b"original")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),["source.png"])
    def test_complete_upload_and_hash(self):
        helper=self.helpers();target=self.root/"new.png"
        self.assertEqual(helper["_copy_upload_with_limit"](file=SimpleNamespace(file=io.BytesIO(b"new")),target=target,max_bytes=100),3)
        self.assertEqual(helper["_source_sha256"](target),hashlib.sha256(b"new").hexdigest())
    def auth(self):
        from backend.services.database import Database
        from backend.services.auth_store import AuthStore
        return AuthStore(Database(self.root/"isolated.sqlite",database_url="sqlite-local-only"),session_ttl_seconds=60)
    def test_session_digest_expiry_revocation_and_legacy_reauth(self):
        auth=self.auth()
        with patch("backend.services.auth_store._now",return_value=100):
            registered=auth.register_user(email="synthetic@example.test",password="Synthetic-only-123",name="Synthetic")
        token=registered["token"]
        connection=auth.db.connect()
        try:
            stored=connection.execute("SELECT token FROM auth_tokens").fetchone()["token"]
            self.assertNotEqual(stored,token);self.assertTrue(stored.startswith("sha256:"))
        finally:connection.close()
        with patch("backend.services.auth_store._now",return_value=120):self.assertIsNotNone(auth.authenticate_token(token))
        with patch("backend.services.auth_store._now",return_value=161):self.assertIsNone(auth.authenticate_token(token))
        with patch("backend.services.auth_store._now",return_value=120):
            auth.logout(token);self.assertIsNone(auth.authenticate_token(token))
        connection=auth.db.connect()
        try:
            connection.execute("INSERT INTO auth_tokens(token,user_id,created_at,last_used_at) VALUES(?,?,?,?)",("legacy-raw",registered["user"]["user_id"],100,100));connection.commit()
        finally:connection.close()
        with patch("backend.services.auth_store._now",return_value=120):self.assertIsNone(auth.authenticate_token("legacy-raw"))
    def test_learning_collection_requires_separate_consent(self):
        import backend.services.chat_learning_store as learning
        path=self.root/"learning.jsonl"
        with patch.object(learning,"_chat_learning_disabled",return_value=False),patch.object(learning,"_learning_path",return_value=path):
            learning.append_chat_learning_event({"global_learning_enabled":True,"message":"synthetic"})
            self.assertFalse(path.exists())
            learning.append_chat_learning_event({"message":"synthetic"},consent={"global_learning_enabled":False})
            self.assertFalse(path.exists())
            learning.append_chat_learning_event({"user_id":"synthetic-user","message":"synthetic"},consent={"global_learning_enabled":True})
            self.assertEqual(len(path.read_text().splitlines()),1)
    def test_operator_allowlist_and_untrusted_forwarded_identity(self):
        ns={"os":SimpleNamespace(getenv=lambda _:"operator-id"),"HTTPException":HTTPException}
        extracted("backend/api/app.py",["_require_operator","_request_rate_limit_key"],ns)
        ns["_require_operator"]({"user_id":"operator-id"})
        with self.assertRaises(HTTPException):ns["_require_operator"]({"user_id":"ordinary-user"})
        request=SimpleNamespace(client=SimpleNamespace(host="198.51.100.9"),headers={"x-forwarded-for":"different"})
        self.assertEqual(ns["_request_rate_limit_key"](request,"Bearer arbitrary"),"ip:198.51.100.9")


def run_tests():
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (HydrologyTests,DetentionTests,SurfaceTests,EgressTests,StorageSecurityTests))
    return unittest.TextTestRunner(verbosity=2).run(suite)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--report",type=Path);args=parser.parse_args()
    output=io.StringIO()
    with redirect_stderr(output):result=run_tests()
    report={"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "exit_code":0 if result.wasSuccessful() else 1,"log":output.getvalue()}
    if args.report:
        with args.report.open("x") as stream:json.dump(report,stream,indent=2)
    print(output.getvalue());print(json.dumps({k:v for k,v in report.items() if k!="log"}))
    raise SystemExit(report["exit_code"])
