"""Report evidence conservatively: an ORT VitisAI node can contain CPU work."""
import json
from pathlib import Path
import re
from pc.multiobject.yolo import digest


def summarize_profile(path):
    events = json.loads(Path(path).read_bytes())
    counts = {}
    for event in events:
        provider = event.get('args', {}).get('provider')
        if event.get('cat') == 'Node' and provider:
            counts[provider] = counts.get(provider, 0)+1
    return {'profile_file': str(path), 'profile_sha256': digest(path), 'ep_node_events': counts,
            'vitis_ep_observed': counts.get('VitisAIExecutionProvider', 0) > 0,
            'npu_execution_verified': False, 'core_mac_coverage': None,
            'reason': 'EP_PROFILE_DOES_NOT_PROVE_INTERNAL_NPU_PLACEMENT',
            'required': ['SDK operator assignment', 'NPU actual-run log', 'core compute mapping review']}


def summarize_sdk_log(path):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    # Only AMD's explicit actual-run message is counted; 'NPU' in a pathname is not proof.
    actual = [int(v) for v in re.findall(r'Actually running on NPU\s*[:=]?\s*(\d+)', text, re.I)]
    return {'log_sha256': digest(path), 'actual_npu_subgraphs_reported': max(actual, default=0),
            'npu_run_observed': any(v > 0 for v in actual), 'core_mac_coverage': None,
            'final_acceptance': False, 'reason': 'CORE_PLACEMENT_AND_QUALITY_REVIEW_REQUIRED'}
