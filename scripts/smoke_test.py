#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "smoke_test.py"
SPEC = importlib.util.spec_from_file_location("douyin_mcp_smoke_module", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load smoke test module from {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
main = MODULE.main


if __name__ == "__main__":
    raise SystemExit(main())
