from pathlib import Path

_core = Path(__file__).with_name("pyfairy_xiangqi_core.py")
if _core.is_file():
    exec(compile(_core.read_text(encoding="utf-8"), str(_core), "exec"), globals())

if __name__ == "__main__":
    main()
