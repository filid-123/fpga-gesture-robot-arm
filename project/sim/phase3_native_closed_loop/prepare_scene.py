"""Prepare a live scene for FPGA UART tests, or explicitly clean it up."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import bootstrap
from executor import CoppeliaScene, FixtureCodec
from run_closed_loop import build_geometry, SCHEMA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    descriptor_path = args.out/"SCENE_DESCRIPTOR.json"
    if args.cleanup:
        scene = CoppeliaScene(json.loads(descriptor_path.read_text(encoding="utf-8")))
        scene.initial = tuple(scene.descriptor["initial_rad"])
        scene.close()
        descriptor_path.unlink()
        print("CLEANED: initial pose restored; temporary bridge/payloads removed")
        return
    if descriptor_path.exists():
        raise RuntimeError("Clean up the previous live descriptor before preparing again")
    args.out.mkdir(parents=True, exist_ok=True)
    scene = CoppeliaScene()
    try:
        cfg, tables, paths, geometry = build_geometry(scene, FixtureCodec())
        scene.reset(geometry["home_rad"], geometry["pick_m"])
        scene.descriptor["initial_rad"] = scene.initial
        descriptor_path.write_text(json.dumps(scene.descriptor, indent=2)+"\n", encoding="utf-8")
        data = {"schema":SCHEMA, "simulation_only":True, "fixture":True,
                "config":asdict(cfg), "tables":asdict(tables), "geometry":geometry,
                "paths":{str(k):[asdict(s) for s in v] for k,v in paths.items()}}
        (args.out/"SIMULATION_CONFIG.json").write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
        print("READY: live scene prepared; keep CoppeliaSim stopped and running")
    except Exception:
        scene.close()
        raise


if __name__ == "__main__":
    main()
