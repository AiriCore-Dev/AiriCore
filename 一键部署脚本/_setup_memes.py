import sys
import os
import zipfile
import tempfile
import importlib.util


def main():
    root = sys.argv[1]
    parts = [
        os.path.join(root, "memes.zip.001"),
        os.path.join(root, "memes.zip.002"),
    ]
    for p in parts:
        if not os.path.isfile(p):
            print("缺少分卷文件: " + p)
            sys.exit(1)

    spec = importlib.util.find_spec("meme_generator")
    if spec is None or spec.origin is None:
        print("当前环境未安装 meme_generator")
        sys.exit(1)
    pkg_dir = os.path.dirname(spec.origin)

    combined = os.path.join(tempfile.gettempdir(), "airicore_memes_all.zip")
    with open(combined, "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

    with zipfile.ZipFile(combined) as z:
        z.extractall(pkg_dir)

    try:
        os.remove(combined)
    except OSError:
        pass

    print("memes extracted to " + os.path.join(pkg_dir, "memes"))


if __name__ == "__main__":
    main()
