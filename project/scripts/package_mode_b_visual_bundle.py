"""Complete original-path visual supplement for the Giao checkout and current pose.

The older AMD prevalidation package is reused unchanged as a base. This adds
the actual web freeze dependencies and the current physical-trial camera pose.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verify_mode_b_visual_bundle import CONFIG, digest, local, verify_current

DOC = 'docs/phase3c/mode_b_visual_bundle_20261029'
BASE = 'artifacts/multiobject/mode_b_amd_20261028_v1.zip'
FREEZE = 'artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json'


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def stage(stage):
    stage.mkdir(parents=True, exist_ok=False)
    from verify_deployment_archive import verify_zip
    verify_zip(ROOT/BASE)
    with zipfile.ZipFile(ROOT/BASE) as z:
        # Already validated member names and manifest in verify_zip.
        z.extractall(stage)
    # Old manifest describes the immutable base, not this augmented bundle.
    (stage/'FILE_MANIFEST.json').rename(stage/'AMD_BASE_FILE_MANIFEST.json')
    def add(name):
        source = local(ROOT, name)
        relative = source.relative_to(ROOT)
        dest = stage/relative
        if dest.exists() and digest(dest) != digest(source):
            raise ValueError('Base/source conflict: '+str(relative))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        return relative.as_posix()
    frozen = json.loads((ROOT/FREEZE).read_bytes())
    add(FREEZE)
    for name, sha in frozen['files_sha256'].items():
        if digest(local(ROOT, name)) != sha:
            raise ValueError('Original frozen dependency changed: '+name)
        add(name)
    # Include the actual module directories; optional training modules don't run
    # during web or replay. No datasets, venvs or motion module are globbed.
    for path in (ROOT/'pc/multiobject').glob('*.py'):
        add(path.relative_to(ROOT).as_posix())
    for path in (ROOT/'web/project-console').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            add(path.relative_to(ROOT).as_posix())
    for name in ['pc/rgb_table_geometry.py', 'pc/rgb_workspace_overlay.py', 'pc/rgb_dshow.py',
                 'pc/native/RgbCameraControls.cs',
                 'scripts/probe_rgb_camera_controls.ps1', 'scripts/set_rgb_camera_exposure.ps1',
                 'scripts/start_project_console.ps1', 'scripts/test_project_console.py',
                 'scripts/test_project_console_vision.py', 'scripts/verify_mode_b_visual_bundle.py',
                 'scripts/replay_mode_b_visual_bundle.py', 'scripts/mode_b_eraser_geometry.py',
                 'scripts/package_mode_b_visual_bundle.py', 'scripts/preview_mode_b.py',
                 'artifacts/phase3c/top_metric_check_20261028/replay_saved_tops.py']:
        add(name)
    historical = 'artifacts/multiobject/eraser_top_repair_20261027/fresh_confirmation_capture/capture.json'
    add(historical)
    for frame in json.loads((ROOT/historical).read_bytes())['frames']:
        add(frame['image'])
    local_profile_path = 'config/ai_pc/mode_b_red_grasp_correction_20261028.json'
    local_profile = json.loads((ROOT/local_profile_path).read_bytes())
    workpath = add(local_profile['workspace_file'])
    work = json.loads(local(ROOT, workpath).read_bytes())
    tablepath = add(work['table_file'])
    table = json.loads(local(ROOT, tablepath).read_bytes())
    intrinsic = add(table['intrinsics_file'])
    direction = add(table['desktop_registration_file'])
    anchor = add(local_profile['successful_native_source_anchor_file'])
    fixtures = []
    # Each source is the exact metric/capture used by a successful physical plan.
    for name in ('red_cube', 'eraser', 'small_canister'):
        planpath = f'docs/phase3c/mode_b_teammate_handoff_20261028/objects/{name}/evidence/PLAN.json'
        plan = json.loads((ROOT/planpath).read_bytes())
        request = Path(plan['source_metric_request_file'])
        metric = request.parent/'METRIC.json'
        record = json.loads(metric.read_bytes())
        capture = Path(record['capture_file'])
        frames = json.loads(capture.read_bytes())['frames']
        sources = []
        add(request.relative_to(ROOT).as_posix())
        add(metric.relative_to(ROOT).as_posix())
        add(capture.relative_to(ROOT).as_posix())
        for row, measured in zip(frames, record['records']):
            add(row['image'])
            add(Path(measured['observation_file']).relative_to(ROOT).as_posix())
            sources.append({'image':row['image'], 'image_sha256':row['image_sha256'],
                            'pixel_sha256':row['pixel_sha256'],
                            'expected_top':measured['top']})
        fixtures.append({'class_name': name, 'frames': sources,
                         'source_metric_file': metric.relative_to(ROOT).as_posix(),
                         'source_metric_sha256': digest(metric),
                         'expected_object_centre_mm': record['object_centre_mm']})
    config = {'schema':'gesture.mode_b.visual_current.v1', 'created_on':'2026-10-29',
              'freeze':FREEZE, 'workspace':workpath, 'current_table':tablepath,
              'current_intrinsics':intrinsic, 'current_table_sha256':work['table_sha256'],
              'local_grasp_anchor_reference':anchor,
              'metric_sample':fixtures[0]['frames'][0]['image'],
              'bound_files_sha256':{p:digest(stage/p) for p in [FREEZE,workpath,tablepath,intrinsic,direction,anchor]},
              'localization_dimensions':{
                  'red_cube':{'shape':'square','size_mm':[30,30,30]},
                  'eraser':{'shape':'rectangle','size_mm':[65,15,15]},
                  'small_canister':{'shape':'circle','size_mm':[25,25,46]}},
              'dimensions_source':'CURRENT_LOCAL_TRIAL_NOMINAL_REGISTERED_NOT_NEW_DEPTH_MEASUREMENT',
              'successful_pose_reference_fixtures':fixtures,
              'metric_localization_accepted':False, 'camera_to_robot_base':None,
              'physical_execution':False, 'web_to_fpga_bridge_implemented':False}
    dest = stage/CONFIG
    dest.parent.mkdir(parents=True,exist_ok=True)
    save(dest,config)
    save(ROOT/CONFIG,config)
    for filename in ['README_CN.md','INTEGRATION_CN.md','FORWARD_TO_TEAMMATE_CN.md']:
        add(DOC+'/'+filename)
    (stage/'START_HERE_CN.md').write_text(
        '# 模式B完整视觉补包\n\n'
        f'先看[交接入口]({DOC}/README_CN.md)，其中列出网页、毫米回放和当前标定。\n\n'
        '这是视觉依赖完整包；网页到FPGA确认/抓放的自动桥接另见集成说明。\n',encoding='utf8')
    verify_current(stage)
    print(json.dumps({'status':'FULL_VISUAL_STAGED','frozen_files':len(frozen['files_sha256']),
                      'current_table_sha256':work['table_sha256'],'fixtures':len(fixtures)}))


def seal(stage, archive):
    if archive.exists() or (stage/'MODE_B_VISUAL_BUNDLE_MANIFEST.json').exists():
        raise ValueError('Fresh sealed bundle required')
    verify_current(stage)
    if not (stage/'handoff/full_visual_verification.json').is_file():
        raise ValueError('Independent runtime verification required before sealing')
    # Keep the inherited AMD verifier usable on this larger extracted package.
    # The complete visual manifest below also binds this compatibility manifest.
    baseline = sorted(p for p in stage.rglob('*') if p.is_file())
    save(stage/'FILE_MANIFEST.json', {'schema':'gesture.mode_b.file_manifest.v1',
         'files':[{'path':p.relative_to(stage).as_posix(),'sha256':digest(p)} for p in baseline]})
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    if any('__pycache__' in p.parts or p.suffix=='.pyc' for p in files):
        raise ValueError('Python cache is not deliverable')
    manifest = {'schema':'gesture.mode_b.visual_bundle_manifest.v1',
                'base_amd_archive':BASE,'base_amd_sha256':digest(ROOT/BASE),
                'files':[{'path':p.relative_to(stage).as_posix(),'sha256':digest(p)} for p in files]}
    file = stage/'MODE_B_VISUAL_BUNDLE_MANIFEST.json'
    save(file,manifest)
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[file]: z.write(p,p.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('CRC failure')
        for row in manifest['files']:
            if hashlib.sha256(z.read(row['path'])).hexdigest()!=row['sha256']:
                raise ValueError('Archive SHA mismatch')
    meta={'status':'COMPLETE_VISUAL_BUNDLE_READY','archive':archive.name,
          'bytes':archive.stat().st_size,'sha256':digest(archive),'files':len(files),
          'physical_execution':False,'web_to_fpga_bridge_implemented':False}
    save(archive.with_suffix('.json'),meta)
    archive.with_suffix('.sha256').write_text(meta['sha256']+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps(meta))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',required=True,type=Path)
    p.add_argument('--seal',type=Path)
    a=p.parse_args()
    seal(a.stage,a.seal) if a.seal else stage(a.stage)
