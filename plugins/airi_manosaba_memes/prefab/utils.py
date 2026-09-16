import struct
from pathlib import Path


def get_png_size(file_path: Path) -> tuple[int, int]:


    with open(file_path, "rb") as f:
        f.seek(16)
        data = f.read(8)
        width, height = struct.unpack(">II", data)
        return width, height
