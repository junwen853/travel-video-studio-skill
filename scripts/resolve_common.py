#!/usr/bin/env python3
"""Shared helpers for DaVinci Resolve scripting."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_API = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting")
SCRIPT_MODULE = SCRIPT_API / "Modules" / "DaVinciResolveScript.py"
SCRIPT_LIB = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")


def configure_resolve_env() -> dict[str, str]:
    os.environ.setdefault("RESOLVE_SCRIPT_API", str(SCRIPT_API))
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(SCRIPT_LIB))
    pythonpath = os.environ.get("PYTHONPATH", "")
    module_path = str(SCRIPT_API / "Modules")
    if module_path not in pythonpath.split(os.pathsep):
        os.environ["PYTHONPATH"] = module_path + (os.pathsep + pythonpath if pythonpath else "")
    return {
        "RESOLVE_SCRIPT_API": os.environ["RESOLVE_SCRIPT_API"],
        "RESOLVE_SCRIPT_LIB": os.environ["RESOLVE_SCRIPT_LIB"],
        "PYTHONPATH": os.environ["PYTHONPATH"],
    }


def load_resolve_module() -> Any:
    configure_resolve_env()
    if not SCRIPT_MODULE.exists():
        raise RuntimeError(f"DaVinciResolveScript.py not found: {SCRIPT_MODULE}")
    module_path = str(SCRIPT_API / "Modules")
    if module_path not in sys.path:
        sys.path.insert(0, module_path)
    import DaVinciResolveScript as module  # type: ignore[import-not-found]
    if not hasattr(module, "scriptapp"):
        raise RuntimeError("Resolve scripting module loaded but scriptapp() is unavailable.")
    return module


def get_resolve() -> Any:
    module = load_resolve_module()
    resolve = module.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("DaVinci Resolve is not reachable. Open Resolve and enable local scripting.")
    return resolve


def seconds_to_frames(seconds: float, fps: float) -> int:
    return int(round(float(seconds) * float(fps)))
