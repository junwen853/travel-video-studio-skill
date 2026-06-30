#!/usr/bin/env python3
"""Check DaVinci Resolve Studio scripting API availability."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from resolve_common import SCRIPT_API, SCRIPT_LIB, SCRIPT_MODULE, configure_resolve_env, get_resolve


def pgrep_resolve() -> list[str]:
    result = subprocess.run(["pgrep", "-af", "DaVinci Resolve|Resolve.app"], check=False, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def build_status() -> dict:
    env = configure_resolve_env()
    status = {
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "install": {
            "appExists": Path("/Applications/DaVinci Resolve/DaVinci Resolve.app").exists(),
            "scriptApiExists": SCRIPT_API.exists(),
            "scriptModuleExists": SCRIPT_MODULE.exists(),
            "scriptLibExists": SCRIPT_LIB.exists(),
        },
        "environment": env,
        "processes": pgrep_resolve(),
        "reachable": False,
        "productName": None,
        "version": None,
        "currentProject": None,
        "currentTimeline": None,
        "currentPage": None,
        "database": None,
        "error": None,
    }
    try:
        resolve = get_resolve()
        status["reachable"] = True
        status["productName"] = resolve.GetProductName()
        status["version"] = resolve.GetVersionString()
        status["currentPage"] = resolve.GetCurrentPage()
        project_manager = resolve.GetProjectManager()
        try:
            status["database"] = project_manager.GetCurrentDatabase()
        except Exception:  # noqa: BLE001
            status["database"] = None
        project = project_manager.GetCurrentProject()
        if project:
            status["currentProject"] = project.GetName()
            timeline = project.GetCurrentTimeline()
            if timeline:
                status["currentTimeline"] = timeline.GetName()
    except Exception as exc:  # noqa: BLE001
        status["error"] = str(exc)
    return status


def print_human(status: dict) -> None:
    print("DaVinci Resolve API status")
    print(f"App installed: {status['install']['appExists']}")
    print(f"Script API: {status['install']['scriptApiExists']}")
    print(f"Script module: {status['install']['scriptModuleExists']}")
    print(f"Fusion script lib: {status['install']['scriptLibExists']}")
    print(f"Running processes: {len(status['processes'])}")
    print(f"Reachable: {status['reachable']}")
    if status["reachable"]:
        print(f"Product: {status['productName']} {status['version']}")
        print(f"Current project: {status['currentProject']}")
        print(f"Current timeline: {status['currentTimeline']}")
    else:
        print(f"Error: {status['error']}")
        print("Next: open DaVinci Resolve and set Preferences > System > General > External scripting to Local.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Resolve scripting API.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()
    status = build_status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print_human(status)
    return 0 if status["reachable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
