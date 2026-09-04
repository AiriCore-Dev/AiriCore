import importlib.util
from pathlib import Path


_core = Path(__file__).resolve().parents[1] / "plugins" / "nonebot_plugin_cchess" / "engine_runtime" / "core.py"
_spec = importlib.util.spec_from_file_location("airi_cchess_engine_core", _core)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
main = _module.main

if __name__ == "__main__":
    main()
