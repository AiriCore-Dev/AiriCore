import asyncio
import os
import time
import pickle
import shutil
import tempfile

from nonebot import get_driver, logger, require
from . import state

driver = get_driver()
timings = require("nonebot_plugin_apscheduler").scheduler

STALE_TURTLE_SECS = 24 * 3600
DATA_DIR = os.path.join('data', 'airi_turtle_soup')
DATA_PATH = os.path.join(DATA_DIR, 'data.pk')

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
            logger.error(f"airi_turtle_soup 存档读取失败: {e}")
            bak = DATA_PATH + '.bak'
            if os.path.exists(bak):
                try:
                    loaded = _try_load(bak)
                    logger.warning("airi_turtle_soup 已从 .bak 备份恢复存档")
                except Exception as e2:
                    logger.error(f"airi_turtle_soup 备份也无法读取: {e2}")
            if loaded is None:
                try:
                    os.replace(DATA_PATH, DATA_PATH + '.corrupt')
                    logger.error(
                        "airi_turtle_soup 坏档已改名为 data.pk.corrupt，"
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
        return
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
            logger.error(f"airi_turtle_soup 存档写入失败: {e}")
            try:
                os.unlink(tmp)
            except OSError:
                pass


async def daily_clear():
    now = int(time.time())
    stale_cutoff = now - STALE_TURTLE_SECS

    stale_groups = []
    for gid, group_data in state.data.get('group', {}).items():
        if not isinstance(group_data, dict):
            continue
        group_data['times'] = 0
        turtle = group_data.get('turtle')
        if isinstance(turtle, dict):
            if turtle.get('create_time', now) < stale_cutoff:
                group_data.pop('turtle', None)
                stale_groups.append(gid)

    if stale_groups:
        logger.info(f"airi_turtle_soup: 清理 {len(stale_groups)} 个超过24小时未完成的游戏")

    await save_to_json()


async def save_data_backup():
    await save_to_json()
    if _load_failed or not os.path.exists(DATA_PATH):
        return
    try:
        shutil.copyfile(DATA_PATH, DATA_PATH + '.bak')
    except Exception as e:
        logger.warning(f"airi_turtle_soup 存档备份失败: {e}")


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
