"""Standard-library verification of the complete visual supplement and current pose."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'config/ai_pc/mode_b_visual_current_20261029.json'


def local(root, name):
    # Original Windows evidence retains backslashes and its exact hash.
    relative = name.replace('\\', '/')
    path = (Path(root)/relative).resolve()
    if ':' in relative or not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Bundle-relative file required: '+name)
    return path


def read(root, name):
    return json.loads(local(root, name).read_bytes())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_current(root=ROOT):
    config = read(root, CONFIG)
    if config.get('schema') != 'gesture.mode_b.visual_current.v1':
        raise ValueError('Current visual binding required')
    for name, sha in config['bound_files_sha256'].items():
        if digest(local(root, name)) != sha:
            raise ValueError('Current visual binding hash mismatch: '+name)
    freeze = read(root, config['freeze'])
    for name, sha in freeze['files_sha256'].items():
        if digest(local(root, name)) != sha:
            raise ValueError('Frozen source missing or changed: '+name)
    work = read(root, config['workspace'])
    table = read(root, work['table_file'])
    if (digest(local(root, work['table_file'])) != work['table_sha256']
            or work['table_sha256'] != config['current_table_sha256']
            or work['table_frame_id'] != 'desk_global_mm'):
        raise ValueError('Current workspace/table binding mismatch')
    for file_key, sha_key in [('intrinsics_file', 'intrinsics_sha256'),
                              ('desktop_registration_file', 'desktop_registration_sha256')]:
        if digest(local(root, table[file_key])) != table[sha_key]:
            raise ValueError('Calibration dependency hash mismatch')
    anchor = read(root, config['local_grasp_anchor_reference'])
    if anchor['table_transform_sha256'] != work['table_sha256']:
        raise ValueError('Pose does not match the successful local grasp anchor')
    return config, freeze, work


def verify_bundle(root=ROOT):
    manifest = read(root, 'MODE_B_VISUAL_BUNDLE_MANIFEST.json')
    for row in manifest['files']:
        if digest(local(root, row['path'])) != row['sha256']:
            raise ValueError('Incomplete or modified visual bundle: '+row['path'])
    config, freeze, _ = verify_current(root)
    return {'status': 'COMPLETE_VISUAL_FILES_AND_CURRENT_POSE_HASHES_PASS',
            'files': len(manifest['files']), 'frozen_files': len(freeze['files_sha256']),
            'workspace': config['workspace'], 'table_sha256': config['current_table_sha256'],
            'web_to_fpga_bridge': 'NOT_IMPLEMENTED_BY_THIS_SUPPLEMENT',
            'physical_execution': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    a = p.parse_args()
    print(json.dumps(verify_bundle(a.root), ensure_ascii=False))
