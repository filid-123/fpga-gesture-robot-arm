"""No-save Jupyter demo entry point for Locator-v16/classifier-v3."""

from __future__ import annotations

import sys

from phase2_l1_v16_v3_live_view import main


def demo_main() -> int:
    if "--no-save" not in sys.argv[1:]:
        sys.argv.append("--no-save")
    return main()


if __name__ == "__main__":
    raise SystemExit(demo_main())
