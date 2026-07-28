import asyncio
import os
import shutil
import pickle
import tempfile

from nonebot import logger, require

from utils import mailer

from . import state
from .state import driver

timings = require("nonebot_plugin_apscheduler").scheduler

DATA_DIR = os.path.join('data', 'airi_wish_bottle')
DATA_PATH = os.path.join(DATA_DIR, 'data.pk')
MAIL_TAG = "airi_wish_bottle"

_load_failed = False
_save_lock = asyncio.Lock()


def _try_load(path):
    with open(path, 'rb') as f:
        loaded = pickle.load(f)
    if not isinstance(loaded, dict):
        raise ValueError('存档结构异常')
    return loaded


@driver.on_startup
async def load_json():
    global _load_failed
    os.makedirs(DATA_DIR, exist_ok=True)

    loaded = None
    if os.path.exists(DATA_PATH):
        try:
            loaded = _try_load(DATA_PATH)
        except Exception as e:
            logger.error(f"airi_wish_bottle 存档读取失败: {e}")
            bak = DATA_PATH + '.bak'
            if os.path.exists(bak):
                try:
                    loaded = _try_load(bak)
                    logger.warning("airi_wish_bottle 已从 .bak 备份恢复存档")
                except Exception as e2:
                    logger.error(f"airi_wish_bottle 备份也无法读取: {e2}")
            if loaded is None:
                try:
                    os.replace(DATA_PATH, DATA_PATH + '.corrupt')
                    logger.error(
                        "airi_wish_bottle 坏档已改名为 data.pk.corrupt，"
                        "本次运行不再写入存档，请人工处理后重启"
                    )
                except OSError:
                    pass
                _load_failed = True

    if loaded is not None:
        state.data.clear()
        state.data.update(loaded)
    elif not _load_failed:
        await save_to_json()


@driver.on_shutdown
async def save_to_json():
    if _load_failed:
        logger.warning("airi_wish_bottle 存档读取失败过，已跳过写入以保护数据")
    else:
        async with _save_lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            snapshot = dict(state.data)
            fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix='.tmp-', suffix='.pk')
            try:
                with os.fdopen(fd, 'wb') as f:
                    pickle.dump(snapshot, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, DATA_PATH)
            except Exception as e:
                logger.error(f"airi_wish_bottle 存档写入失败: {e}")
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    await flush_email_queue()


async def email_login():
    ok, message = await mailer.probe()
    return message


async def flush_email_queue():
    if not state.email_list:
        return "邮件队列为空"
    sent, total, err = await mailer.flush_queue(state.email_list, MAIL_TAG)
    if err and sent < total:
        return f"发送失败（成功 {sent} 封，剩余 {len(state.email_list)} 封）：{err}"
    return f"成功发送 {sent} 封邮件"


async def daily_clear():
    state.data["comments_daily"] = {}
    state.data["drop_daily"] = []
    await save_to_json()


async def save_data_backup():
    await save_to_json()
    if _load_failed or not os.path.exists(DATA_PATH):
        return
    try:
        shutil.copyfile(DATA_PATH, DATA_PATH + '.bak')
    except Exception as e:
        logger.warning(f"airi_wish_bottle 存档备份失败: {e}")


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
