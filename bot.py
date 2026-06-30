#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
FLUSH_INTERVAL = 30 * 60      # 半小时落盘一次
RETENTION_DAYS = 7            # 日志保留 7 天


class BufferedLogSink:
    """把日志先缓存在内存，定时或关闭时再统一写入文件。"""

    def __init__(self, name, flush_interval=FLUSH_INTERVAL):
        self.name = name                  # error / info / warning
        self.flush_interval = flush_interval
        self.buffer = []
        self.lock = threading.Lock()
        self.timer = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._schedule()

    def __call__(self, message):
        # message 是 loguru 已格式化好的字符串（含换行）
        with self.lock:
            self.buffer.append(str(message))

    def flush(self):
        with self.lock:
            if not self.buffer:
                return
            chunk = "".join(self.buffer)
            self.buffer.clear()
        # 按天分文件，文件名形如 info_2026-06-19.log
        path = LOG_DIR / f"{self.name}_{datetime.now():%Y-%m-%d}.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(chunk)
        self._cleanup()

    def _cleanup(self):
        """删除超过保留期的旧日志。"""
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


# 注册三个级别的缓冲 sink
_sinks = []
for level in ("ERROR", "INFO", "WARNING"):
    sink = BufferedLogSink(level.lower())
    logger.add(sink, level=level, format=default_format)
    _sinks.append(sink)


@driver.on_shutdown
async def _flush_logs_on_shutdown():
    # nonebot 关闭时把内存里剩余的日志全部落盘
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
