import importlib
import sys
import types
from pathlib import Path


def run():
    package_name = '_airi_astral_party_account_tool'
    package = types.ModuleType(package_name)
    package.__path__ = [str(Path(__file__).resolve().parent)]
    sys.modules[package_name] = package
    return importlib.import_module(package_name + '.account_setup').main()


if __name__ == '__main__':
    sys.exit(run())
