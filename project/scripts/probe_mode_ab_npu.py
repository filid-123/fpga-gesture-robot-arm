"""Register and enumerate NPU only; no camera, FPGA or robot access."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_ab.winml import NpuCatalog

if __name__ == '__main__':
    with NpuCatalog() as runtime:
        result = runtime.ready()
        folder = ROOT/'board_evidence/mode_ab_v0_1_0'
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'npu_provider.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result))
