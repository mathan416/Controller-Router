#!/usr/bin/env python3
"""Vendor the exact shared Router package into R.O.B. Vision and VirtualGlove."""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("__init__.py", "controller_router.py", "merged_gamepad.py", "storage.py",
         "retroarch_udev.py", "virtual_sources.py", "LICENSE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a vendored copy differs")
    parser.add_argument("--rob-vision", type=Path, default=ROOT.parent / "rob-vision")
    parser.add_argument("--virtualglove", type=Path, required=True)
    args = parser.parse_args()
    targets = (args.rob_vision / "router_shared", args.virtualglove / "src/router_shared")
    if not (args.rob_vision / "scripts/install.py").is_file():
        parser.error("R.O.B. Vision repository was not found")
    if not (args.virtualglove / "src/virtualglove/controller_router.py").is_file():
        parser.error("VirtualGlove repository was not found")
    drift = []
    for target in targets:
        if not args.check:
            target.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            source, destination = ROOT / "router_shared" / name, target / name
            if args.check:
                if not destination.is_file() or not filecmp.cmp(source, destination, shallow=False):
                    drift.append(str(destination))
            else:
                shutil.copy2(source, destination)
    if drift:
        parser.exit(1, "Router library copies differ:\n" + "\n".join(drift) + "\n")
    print("Router library copies match" if args.check else "Router library vendored into both projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
