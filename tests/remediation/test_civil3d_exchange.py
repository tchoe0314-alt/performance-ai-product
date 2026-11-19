import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from backend.planning.landxml_exchange import build_landxml_exchange, NS, snapshot_grid
from backend.services.artifact_service import ArtifactService


def known_model():
    return {'units':'ft','project_name':'Synthetic handoff','meta':{
        'grading':{'proposed_surface':{'x_min':1000,'y_min':2000,'cell_size':50,'nrows':2,'ncols':3,'values':[[105,104.5,104],[106,105.5,105]]}},
        'storm_pipes':{'structures':[
            {'id':'IN-2','x':1000,'y':2000,'rim_elevation_ft':105,'invert_elevation_ft':100,'diameter_ft':4},
            {'id':'MH-3','x':1100,'y':2000,'rim_elevation_ft':104,'invert_elevation_ft':99,'diameter_ft':4}],
            'segments':[{'id':'P-2','from_node':'IN-2','to_node':'MH-3','length_ft':100,'diameter_in':18,'invert_start_ft':100,'invert_end_ft':99,'slope_ft_ft':.01,'path':[[1000,2000,100],[1100,2000,99]]}]}}}


def inspect(xml):
    return ET.fromstring(xml), {'l':NS}


def test_surface_network_original_and_revised_after_json_reload(tmp_path):
    model=known_model(); service=ArtifactService(tmp_path)
    for revised in (False,True):
        if revised:
            s=model['meta']['storm_pipes'];s['structures'][0]['x']=1020
            p=s['segments'][0];p.update(length_ft=80,diameter_in=24,slope_ft_ft=.0125,path=[[1020,2000,100],[1100,2000,99]])
        # Exact persisted exchange input; actual project-store journey below.
        model=json.loads(json.dumps(model))
        path=service.export_landxml(user_id='synthetic',final_plan=model)
        root,ns=inspect(path.read_text())
        assert root.find('l:Units/l:Imperial',ns).get('linearUnit')=='foot'
        pts=root.findall('.//l:Surface//l:P',ns);faces=root.findall('.//l:Surface//l:F',ns)
        assert len(pts)==6 and len(faces)==4
        assert pts[0].text=='2000 1000 105' and pts[-1].text=='2050 1100 105'
        pipe=root.find('.//l:Pipe',ns)
        assert pipe.get('refStart')=='IN-2' and pipe.get('refEnd')=='MH-3'
        assert float(pipe.get('slope'))==pytest.approx(1.25 if revised else 1.0)
        assert float(pipe.find('l:CircPipe',ns).get('diameter'))==(2 if revised else 1.5)
        assert [float(i.get('elev')) for i in root.findall('.//l:Invert',ns)]==[100,99]
        assert root.find('.//l:Struct/l:Center',ns).text==('2000 1020' if revised else '2000 1000')


@pytest.mark.parametrize('case',['missing_invert','missing_ref','stale_length','stale_slope','bad_surface','cell_surface','bent_pipe','wrong_z','unknown_units'])
def test_export_rejects_incomplete_or_inconsistent_model(case):
    m=known_model();p=m['meta']['storm_pipes']['segments'][0];s=m['meta']['grading']['proposed_surface']
    if case=='missing_invert':del p['invert_start_ft']
    elif case=='missing_ref':p['from_node']='absent'
    elif case=='stale_length':p['length_ft']=80
    elif case=='stale_slope':p['slope_ft_ft']=.02
    elif case=='bad_surface':s['values'][0][0]=float('nan')
    elif case=='cell_surface':s['sampling']='cells'
    elif case=='bent_pipe':p['path'].insert(1,[1050,2010,99.5])
    elif case=='wrong_z':p['path'][0][2]=0
    else:m['units']='unknown'
    with pytest.raises(ValueError):build_landxml_exchange(m)


def test_grid_snapshot_preserves_exact_values_independently():
    from engines.surface_engine import GridSurface
    grid=GridSurface(x_min=0,y_min=0,x_max=20,y_max=20,cell_size=10,nrows=3,ncols=3,values=[[100.123456789]*3 for _ in range(3)])
    saved=snapshot_grid(grid)
    assert saved['values'][0][0]==100.123456789
    grid.values[0][0]=0
    assert saved['values'][0][0]==100.123456789


def test_project_revision_reopen_and_reexport_preserves_changed_network(tmp_path):
    from backend.services.auth_store import AuthStore
    from backend.services.database import Database
    from backend.services.project_store import ProjectStore
    from backend.services.canonical_canvas import with_canvas_snapshot
    from backend.services.canonical_results import ENGINE_REVISION
    from backend.application.artifact_workflows import export_dxf_artifact
    from engines.pipe_engine import PipeEngine
    db=Database(tmp_path/'handoff.db');auth=AuthStore(db)
    user=auth.register_user(email='handoff@example.test',password='Disposable-123',name='Synthetic handoff')['user']['user_id']
    store=ProjectStore(db);model=known_model()
    source=with_canvas_snapshot({'manual_fields':{'units':'ft','site_objects':[]},'meta':{'synthetic_exchange_input':copy.deepcopy(model)}})
    project=store.save_project(user_id=user,project_id=None,name='Handoff',project_input=source)
    pid=project['project_id'];service=ArtifactService(tmp_path/'artifacts')
    for revised in (False,True):
        if revised:
            model['meta']['storm_pipes']['structures'][0]['x']=1020
            model['meta']['storm_pipes']['segments'][0].update(length_ft=80,diameter_in=24,slope_ft_ft=.0125,path=[[1020,2000,100],[1100,2000,99]])
            source=with_canvas_snapshot({'manual_fields':{'units':'ft','site_objects':[]},'meta':{'synthetic_exchange_input':copy.deepcopy(model)}})
            store.save_project_shell(user_id=user,project_id=pid,name='Handoff revised',project_input=source,
                expected_revision=store.get_project(user_id=user,project_id=pid)['revision_token'])
        pipe=model['meta']['storm_pipes']['segments'][0]
        q=PipeEngine.full_flow_capacity_cfs(pipe['diameter_in'],pipe['slope_ft_ft'],.013)
        assert q==pytest.approx(25.292611460686935 if revised else 10.50433834026563)
        result=store.save_calculation_result(user_id=user,project_id=pid,source_input=source,
            result={'success':True,'metadata':{'calculation_engine_revision':ENGINE_REVISION},'final_plan':copy.deepcopy(model)})
        reopened=ProjectStore(db).get_project(user_id=user,project_id=pid)
        assert reopened['project_input']['meta']['synthetic_exchange_input']['meta']['storm_pipes']==model['meta']['storm_pipes']
        # The synthetic numerical fixture is not an approved engineering run.
        # Preserve the application gate, then inspect a diagnostic serializer
        # export of the actually reopened calculation record.
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as blocked:
            export_dxf_artifact(artifact_service=service,project_store=store,user_id=user,project_id=pid,result_data=result,export_scope='review',export_format='landxml')
        assert blocked.value.status_code==409
        restored=ProjectStore(db).get_project_latest_result(user_id=user,project_id=pid)
        assert restored['final_plan']['meta']['storm_pipes']==model['meta']['storm_pipes']
        path=service.export_landxml(user_id=user,final_plan=restored['final_plan'])
        root,ns=inspect(path.read_text());node=root.find('.//l:Pipe',ns)
        assert float(node.get('length'))==(80 if revised else 100)
        assert node.get('refStart')=='IN-2'
        assert float(node.find('l:CircPipe',ns).get('diameter'))==(2 if revised else 1.5)
        assert root.find('.//l:Struct/l:Center',ns).text==('2000 1020' if revised else '2000 1000')


def test_standard_landxml_import_uses_northing_easting(tmp_path):
    from backend.planning.landxml_io import import_landxml
    path=tmp_path/'surface.xml';path.write_text(build_landxml_exchange(known_model()))
    surface=import_landxml(path)['surfaces'][0]
    assert surface['points'][0]['x']==1000
    assert surface['points'][0]['y']==2000
    assert surface['points'][0]['z']==105


def test_explicit_3d_dxf_geometry_preserves_invert_vertices(tmp_path):
    import ezdxf
    from output.dxf_exporter import save_dxf
    plan={'project_name':'3D linework only','units':'ft','actions':[{'task':'polyline','layer':'STORM','points':[[1000,2000,100],[1100,2000,99]]}],'meta':{}}
    path=tmp_path/'pipe.dxf';save_dxf(plan,filename=str(path))
    d=ezdxf.readfile(path);lines=list(d.modelspace().query('POLYLINE'))
    assert len(lines)==1 and lines[0].is_3d_polyline
    assert [tuple(v.dxf.location) for v in lines[0].vertices]==[(1000,2000,100),(1100,2000,99)]


def test_mutated_xml_cannot_pass_local_contract():
    from backend.planning.export_external_verification import verify_landxml_export
    original=build_landxml_exchange(known_model())
    for xml in [original.replace('refEnd="MH-3"','refEnd="missing"'), original.replace('elev="100"','elev="NaN"'), original.replace('2000 1000 105','NaN 1000 105'), original.replace('linearUnit="foot"','linearUnit="mile"')]:
        assert not verify_landxml_export(xml)['local_contract_verified']


def test_unknown_coordinate_unit_is_not_relabelled_as_feet():
    m=known_model();m['meta']['coordinate_system']={'horizontal_units':'USSurveyFoot'}
    with pytest.raises(ValueError,match='explicit conversion'):build_landxml_exchange(m)


def test_complete_authored_review_pipe_is_preserved_as_its_own_network():
    model = known_model()
    model['meta']['review_pipe_network'] = {
        'review_only': True,
        'construction_release_allowed': False,
        'structures': [
            {'id':'AUTH-A','x':600,'y':420,'rim_elevation_ft':100,'sump_elevation_ft':89},
            {'id':'AUTH-B','x':760,'y':500,'rim_elevation_ft':99,'sump_elevation_ft':87.5},
        ],
        'segments': [{
            'id':'SYN-STORM-PIPE-1','canonical_id':'SYN-STORM-PIPE-1',
            'from_node':'AUTH-A','to_node':'AUTH-B','path':[[600,420],[760,500]],
            'length_ft':178.885,'diameter_in':18,'slope_ft_ft':.01,
            'invert_start_ft':90,'invert_end_ft':88.21115,
            'review_required':True,'construction_release_allowed':False,
        }],
    }
    root, ns = inspect(build_landxml_exchange(model))
    authored = next(pipe for pipe in root.findall('.//l:Pipe', ns) if pipe.get('name') == 'SYN-STORM-PIPE-1')

    assert authored.get('length') == '178.885'
    assert authored.get('slope') == '1'
    assert authored.get('civoraCanonicalId') == 'SYN-STORM-PIPE-1'
    assert authored.get('civoraReviewOnly') == 'true'
    assert authored.get('civoraConstructionReleaseAllowed') == 'false'
    assert authored.get('civoraCivil3dVerificationStatus') == 'not_verified'
    assert authored.find('l:CircPipe', ns).get('diameter') == '1.5'
    props = {node.get('label'): node.get('value') for node in authored.findall('l:Feature/l:Property', ns)}
    assert props['canonical_id'] == 'SYN-STORM-PIPE-1'
    assert props['review_only'] == 'true'


def test_incomplete_authored_review_pipe_is_not_silently_omitted():
    model = known_model()
    model['meta']['review_pipe_network'] = {
        'review_only': True,
        'construction_release_allowed': False,
        'structures': [],
        'segments': [{'id':'AUTH-INCOMPLETE','length_ft':100,'diameter_in':18}],
    }
    with pytest.raises(ValueError, match='connected pipes and structures'):
        build_landxml_exchange(model)
