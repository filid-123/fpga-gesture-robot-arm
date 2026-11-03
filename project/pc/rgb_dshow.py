"""Windows driver identity and exact-path exposure writes, without OpenCV mode guesses."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def _powershell(script, *args):
    result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                             '-File', str(ROOT/'scripts'/script), *map(str, args)],
                            capture_output=True, timeout=20)
    # JSON is ASCII escaped by ConvertTo-Json on the supported driver fields.
    output = result.stdout.decode('utf-8-sig', errors='replace')
    try:
        record = json.loads(output)
    except ValueError as exc:
        raise RuntimeError('DirectShow helper failed: '+result.stderr.decode(errors='replace')) from exc
    if result.returncode:
        raise RuntimeError('DirectShow operation unverified: '+json.dumps(record))
    return record


def inspect_devices():
    return _powershell('probe_rgb_camera_controls.ps1')['devices']


def select_device(devices, device_path):
    matches = [d for d in devices if d['DevicePath'].casefold() == device_path.casefold()]
    if len(matches) != 1:
        raise ValueError('Selected camera absent or ambiguous; reconnect and inspect devices')
    return matches[0]


def set_exposure(device_path, value, flags=2):
    return _powershell('set_rgb_camera_exposure.ps1', '-DevicePath', device_path,
                       '-Exposure', value, '-Flags', flags)


def exposure_values(control, stops=3):
    """At most three supported log2 steps darker than the stored driver value."""
    if (not control.get('Supported') or not control['Capabilities'] & 2
            or control['Flags'] not in (1, 2) or control['Step'] <= 0):
        raise ValueError('Hardware exposure/manual control or original mode unavailable')
    # Auto readback can be the last manual register, not the integration time.
    start = control.get('DefaultValue', control['Value']) if control['Flags'] == 1 else control['Value']
    if not control['Minimum'] <= start <= control['Maximum']:
        raise ValueError('Invalid driver exposure readback')
    return [start-i*control['Step'] for i in range(stops+1)
            if start-i*control['Step'] >= control['Minimum']]
