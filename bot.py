import time
import threading
from pathlib import Path
from datetime import datetime, timedelta

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.log import default_format, logger

nonebot.init()
app = nonebot.get_asgi()

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)
config = driver.config
config.nb2_path = Path(__file__).parent

LOG_DIR = Path("logs")
FLUSH_INTERVAL = 30 * 60
RETENTION_DAYS = 7
MAX_BUFFER_SIZE = 10000


class BufferedLogSink:

    def __init__(self, name, flush_interval=FLUSH_INTERVAL):
        self.name = name
        self.flush_interval = flush_interval
        self.buffer = []
        self.lock = threading.Lock()
        self.timer = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._schedule()

    def __call__(self, message):
        with self.lock:
            self.buffer.append(str(message))
            if len(self.buffer) >= MAX_BUFFER_SIZE:
                self._flush_unlocked()

    def flush(self):
        with self.lock:
            self._flush_unlocked()

    def _flush_unlocked(self):
        if not self.buffer:
            return
        chunk = "".join(self.buffer)
        self.buffer.clear()
        path = LOG_DIR / f"{self.name}_{datetime.now():%Y-%m-%d}.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(chunk)
        self._cleanup()

    def _cleanup(self):
        cutoff = time.time() - RETENTION_DAYS * 86400
        for old in LOG_DIR.glob(f"{self.name}_*.log"):
            if old.stat().st_mtime < cutoff:
                old.unlink(missing_ok=True)

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


_sinks = []
for level in ("ERROR", "INFO", "WARNING"):
    sink = BufferedLogSink(level.lower())
    logger.add(sink, level=level, format=default_format)
    _sinks.append(sink)


@driver.on_shutdown
async def _flush_logs_on_shutdown():
    for sink in _sinks:
        sink.close()


if __name__ == "__main__":
    nonebot.load_plugin("nonebot_plugin_localstore")
    nonebot.load_plugins("plugins")
    nonebot.run(
        app="__mp_main__:app",
        ssl_keyfile="./ssl/privkey.key",
        ssl_certfile="./ssl/fullchain.pem",
    )
