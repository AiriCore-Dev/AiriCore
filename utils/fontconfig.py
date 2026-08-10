import os
import sys
from pathlib import Path


def configure_fontconfig():
    if sys.platform != "linux":
        return
    config_path = Path(__file__).with_name("fontconfig.conf")
    if config_path.is_file():
        os.environ.setdefault("FONTCONFIG_FILE", str(config_path))
