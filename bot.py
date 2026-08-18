import os
import re
import sys
import time
import shutil
import threading
from pathlib import Path
from datetime import datetime

from utils.fontconfig import configure_fontconfig

configure_fontconfig()

CHILD_ARG = "--airicore-child"

if __name__ == "__main__" and CHILD_ARG not in sys.argv:
    _self = os.path.abspath(__file__)
    while 1:
        os.system(f'"{sys.executable}" "{_self}" {CHILD_ARG}')
        print("Restarting...")
        time.sleep(2)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BANNER_ART = (
    "   ░███    ░██         ░██  ░██████",
    "  ░██░██                   ░██   ░██",
    " ░██  ░██  ░██░██░████ ░██░██         ░███████  ░██░████  ░███████",
    "░█████████ ░██░███     ░██░██        ░██    ░██ ░███     ░██    ░██",
    "░██    ░██ ░██░██      ░██░██        ░██    ░██ ░██      ░█████████",
    "░██    ░██ ░██░██      ░██ ░██   ░██ ░██    ░██ ░██      ░██",
    "░██    ░██ ░██░██      ░██  ░██████   ░███████  ░██       ░███████",
)

BANNER_ASCII_MAP = {"░": ":", "▒": "+", "▓": "*", "█": "#"}

BANNER_ASCII = tuple(
    "".join(BANNER_ASCII_MAP.get(char, char) for char in row) for row in BANNER_ART
)

BANNER_SHADE_LEVEL = {
    "░": 0.62,
    "▒": 0.78,
    "▓": 0.9,
    "█": 1.0,
    ":": 0.62,
    "+": 0.78,
    "*": 0.9,
    "#": 1.0,
}
BANNER_ROW_ALPHA = (0.72, 0.84, 0.94, 1.0, 0.94, 0.84, 0.74)
BANNER_VERSION_RGB = (255, 255, 255)
BANNER_VERSION_KEY = "airicore_version"
BRAND_LABEL = "AiriCore"
BANNER_HUE_SPAN = 0.78
BANNER_ROW_SKEW = 0.055
BANNER_FRAMES = 34
BANNER_FRAME_DELAY = 0.055

_BANNER_FLAG = "AIRICORE_BANNER_SHOWN"


def _hsv_rgb(hue, sat, val):
    hue = hue % 1.0
    sector = int(hue * 6) % 6
    offset = hue * 6 - int(hue * 6)
    high = val
    low = val * (1 - sat)
    fall = val * (1 - sat * offset)
    rise = val * (1 - sat * (1 - offset))
    table = (
        (high, rise, low),
        (fall, high, low),
        (low, high, rise),
        (low, fall, high),
        (rise, low, high),
        (high, low, fall),
    )
    return tuple(max(0, min(255, round(channel * 255))) for channel in table[sector])


def _enable_ansi():
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _banner_color_mode():
    if os.environ.get("NO_COLOR"):
        return "plain"
    if not sys.stdout.isatty():
        return "plain"
    if os.environ.get("TERM") == "dumb":
        return "plain"
    if not _enable_ansi():
        return "plain"
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "true"
    return "256"


def _cube_index(value):
    steps = (0, 95, 135, 175, 215, 255)
    best = 0
    for index in range(1, 6):
        if abs(steps[index] - value) < abs(steps[best] - value):
            best = index
    return best


def _banner_bg(rgb, mode):
    r, g, b = rgb
    if mode == "true":
        return f"\033[48;2;{r};{g};{b}m"
    slot = 16 + 36 * _cube_index(r) + 6 * _cube_index(g) + _cube_index(b)
    return f"\033[48;5;{slot}m"


def _banner_fg(rgb, mode):
    r, g, b = rgb
    if mode == "true":
        return f"\033[38;2;{r};{g};{b}m"
    slot = 16 + 36 * _cube_index(r) + 6 * _cube_index(g) + _cube_index(b)
    return f"\033[38;5;{slot}m"


def _paint_banner_row(row, index, width, phase, mode):
    if mode == "plain":
        return row
    alpha = BANNER_ROW_ALPHA[index % len(BANNER_ROW_ALPHA)]
    out = []
    active = None
    for column, cell in enumerate(row):
        if cell == " ":
            if active is not None:
                out.append("\033[0m")
                active = None
            out.append(cell)
            continue
        hue = phase + column / max(width, 1) * BANNER_HUE_SPAN - index * BANNER_ROW_SKEW
        value = alpha * BANNER_SHADE_LEVEL.get(cell, 0.85)
        code = _banner_fg(_hsv_rgb(hue, 0.82, value), mode)
        if code != active:
            out.append(code)
            active = code
        out.append(cell)
    if active is not None:
        out.append("\033[0m")
    return "".join(out)


def _read_version():
    env_name = os.environ.get("ENVIRONMENT", "prod")
    root = Path(__file__).parent
    for candidate in (root / f".env.{env_name}", root / ".env"):
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip().lower() != BANNER_VERSION_KEY:
                continue
            value = value.strip().split(" #")[0].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value.lower().startswith(BRAND_LABEL.lower()):
                value = value[len(BRAND_LABEL):].strip()
            if value:
                return value
    return ""


def _console_utf8():
    if os.environ.get("AIRI_BANNER_ASCII") == "1":
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        return ctypes.windll.kernel32.GetConsoleOutputCP() == 65001
    except Exception:
        return False


def _banner_art(mode):
    return BANNER_ART if _console_utf8() else BANNER_ASCII


def _paint_version_row(text, width, mode):
    pad = max(width - len(text), 0)
    if mode == "plain":
        return " " * pad + text
    return " " * pad + _banner_fg(BANNER_VERSION_RGB, mode) + text + "\033[0m"


def _render_banner_frame(art, width, phase, mode, version=""):
    lines = [
        _paint_banner_row(row, index, width, phase, mode) for index, row in enumerate(art)
    ]
    if version:
        lines.append(_paint_version_row(version, width, mode))
    return "\n".join(lines)


def print_banner():
    if os.environ.get(_BANNER_FLAG):
        return
    os.environ[_BANNER_FLAG] = "1"
    mode = _banner_color_mode()
    columns = shutil.get_terminal_size((80, 24)).columns
    art = _banner_art(mode)
    version = _read_version()
    banner_width = max(len(row) for row in art)
    if version and len(version) > banner_width:
        version = version[:banner_width]
    height = len(art) + (1 if version else 0)
    animate = mode != "plain" and os.environ.get("AIRI_BANNER_ANIMATE", "1") != "0"
    print()
    if animate:
        for frame in range(BANNER_FRAMES):
            sys.stdout.write(
                _render_banner_frame(art, banner_width, frame / BANNER_FRAMES, mode, version)
            )
            sys.stdout.flush()
            if frame < BANNER_FRAMES - 1:
                sys.stdout.write(f"\033[{height - 1}A\r")
                time.sleep(BANNER_FRAME_DELAY)
            else:
                sys.stdout.write("\n")
    else:
        print(_render_banner_frame(art, banner_width, 0.0, mode, version))
    subtitle = f"AiriCore Bot   Python {sys.version.split()[0]}   {datetime.now():%Y-%m-%d %H:%M:%S}"
    if mode == "plain":
        print(subtitle)
    else:
        cells = min(banner_width, max(columns - 1, 8))
        bar = []
        active = None
        for step in range(cells):
            code = _banner_bg(_hsv_rgb(step / max(cells - 1, 1) * BANNER_HUE_SPAN, 0.72, 0.62), mode)
            if code != active:
                bar.append(code)
                active = code
            bar.append(" ")
        print("".join(bar) + "\033[0m")
        print(f"\033[1;38;5;219m{subtitle}\033[0m")
    print()
    sys.stdout.flush()


print_banner()

import nonebot
from nonebot.log import default_format, logger

BRAND_NAME = BRAND_LABEL
_BRAND_PATTERN = re.compile(r"(?<![\w.])[Nn]one[Bb]ot(?![\w]|\.[A-Za-z_])")
_upstream_patcher = getattr(nonebot, "_log_patcher", None)


def _brand_patcher(record):
    if _upstream_patcher is not None:
        try:
            _upstream_patcher(record)
        except Exception:
            pass
    name = record.get("name")
    if name in ("nonebot", "NoneBot"):
        record["name"] = BRAND_NAME
    message = record.get("message")
    if message and "one" in message.lower():
        record["message"] = _BRAND_PATTERN.sub(BRAND_NAME, message)


nonebot._log_patcher = _brand_patcher
logger.configure(patcher=_brand_patcher)

nonebot.init()
app = nonebot.get_asgi()

from utils.onebot_query import Adapter as ONEBOT_V11Adapter, install_event_observer

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)
install_event_observer()
config = driver.config
config.nb2_path = Path(__file__).parent

LOG_DIR = Path("logs")
FLUSH_INTERVAL = 30 * 60
RETENTION_DAYS = 7
MAX_BUFFER_SIZE = 10000
CLEANUP_INTERVAL = 12 * 3600


class BufferedLogSink:

    def __init__(self, name, flush_interval=FLUSH_INTERVAL):
        self.name = name
        self.flush_interval = flush_interval
        self.buffer = []
        self.lock = threading.Lock()
        self.timer = None
        self.last_cleanup = 0.0
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._schedule()

    def __call__(self, message):
        pending = None
        with self.lock:
            self.buffer.append((f"{datetime.now():%Y-%m-%d}", str(message)))
            if len(self.buffer) >= MAX_BUFFER_SIZE:
                pending = self.buffer
                self.buffer = []
        if pending:
            self._write(pending)

    def flush(self):
        with self.lock:
            pending = self.buffer
            self.buffer = []
        if pending:
            self._write(pending)

    def _write(self, pending):
        grouped = {}
        for day, text in pending:
            grouped.setdefault(day, []).append(text)
        for day, texts in grouped.items():
            path = LOG_DIR / f"{self.name}_{day}.log"
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write("".join(texts))
            except OSError:
                pass
        self._cleanup()

    def _cleanup(self):
        now = time.time()
        if now - self.last_cleanup < CLEANUP_INTERVAL:
            return
        self.last_cleanup = now
        cutoff = now - RETENTION_DAYS * 86400
        for old in LOG_DIR.glob(f"{self.name}_*.log"):
            try:
                if old.stat().st_mtime < cutoff:
                    old.unlink(missing_ok=True)
            except OSError:
                continue

    def _schedule(self):
        self.timer = threading.Timer(self.flush_interval, self._on_timer)
        self.timer.daemon = True
        self.timer.start()

    def _on_timer(self):
        self.flush()
        self._schedule()

    def close(self):
        if self.timer:
            self.timer.cancel()
        self.flush()


def _level_range(low, high=None):
    def _filter(record):
        no = record["level"].no
        if no < low:
            return False
        return high is None or no < high

    return _filter


_LEVEL_NO = {"INFO": 20, "WARNING": 30, "ERROR": 40}

_sinks = []
for level, rng in (
    ("ERROR", (_LEVEL_NO["ERROR"], None)),
    ("INFO", (_LEVEL_NO["INFO"], _LEVEL_NO["WARNING"])),
    ("WARNING", (_LEVEL_NO["WARNING"], _LEVEL_NO["ERROR"])),
):
    sink = BufferedLogSink(level.lower())
    logger.add(sink, level=level, format=default_format, filter=_level_range(*rng))
    _sinks.append(sink)


@driver.on_shutdown
async def _flush_logs_on_shutdown():
    for sink in _sinks:
        sink.close()


_bg_tasks = set()


def _compile_utils():
    import compileall

    try:
        ok = compileall.compile_dir(
            str(Path(__file__).resolve().parent / "utils"),
            quiet=1,
            force=False,
            optimize=0,
        )
    except Exception as e:
        logger.warning(f"启动编译 utils 失败: {e}")
        return False
    if not ok:
        logger.warning("启动编译 utils 未完全成功")
    return ok


@driver.on_startup
async def _preload_caches_on_startup():
    import asyncio

    from utils.cache import run_and_log

    task = asyncio.create_task(asyncio.to_thread(run_and_log))
    _bg_tasks.add(task)

    def _done(t):
        _bg_tasks.discard(t)
        try:
            t.result()
        except Exception as e:
            logger.error(f"缓存预热任务异常: {e}")

    task.add_done_callback(_done)


@driver.on_startup
async def _start_loop_monitor():
    try:
        from utils import loop_monitor

        loop_monitor.start()
    except Exception as e:
        logger.warning(f"运行状态监控启动失败: {e}")


@driver.on_shutdown
async def _stop_loop_monitor():
    try:
        from utils import loop_monitor

        loop_monitor.stop()
    except Exception:
        pass


if __name__ == "__main__":
    _compile_utils()
    nonebot.load_plugin("nonebot_plugin_localstore")
    nonebot.load_plugins("plugins")
    run_kwargs = {"app": "__mp_main__:app"}
    enable_ssl = str(getattr(driver.config, "enable_ssl", False)).lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    if enable_ssl:
        run_kwargs.update(
            ssl_keyfile="./utils/ssl/privkey.key",
            ssl_certfile="./utils/ssl/fullchain.pem",
        )
    nonebot.run(**run_kwargs)
