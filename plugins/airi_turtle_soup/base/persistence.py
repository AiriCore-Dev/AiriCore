import os
import time
import pickle
import shutil
from nonebot import get_driver, require
from . import state

driver = get_driver()
timings = require("nonebot_plugin_apscheduler").scheduler

STALE_TURTLE_SECS = 24 * 3600

@driver.on_startup
async def load_json():
    try:
        with open(os.path.join('data', 'airi_turtle_soup', 'data.pk'), 'rb') as f:
            state.data = pickle.load(f)
    except:
        os.makedirs(os.path.join('data', 'airi_turtle_soup'), exist_ok=True)
        await save_to_json()

@driver.on_shutdown
async def save_to_json():
    with open(os.path.join('data', 'airi_turtle_soup', 'data.pk'), 'wb') as f:
        pickle.dump(state.data, f)

async def daily_clear():
    now = int(time.time())
    stale_cutoff = now - STALE_TURTLE_SECS

    if 'group' in state.data:
        stale_groups = []
        for gid in state.data['group']:
            group_data = state.data['group'][gid]
            group_data['times'] = 0

            if 'turtle' in group_data:
                create_time = group_data['turtle'].get('create_time', now)
                if create_time < stale_cutoff:
                    del group_data['turtle']
                    stale_groups.append(gid)

        if stale_groups:
            from nonebot import logger
            logger.info(f"airi_turtle_soup: 清理 {len(stale_groups)} 个超过24小时未完成的游戏")

    await save_to_json()

async def save_data_backup():
    await save_to_json()
    shutil.copyfile(os.path.join('data', 'airi_turtle_soup', 'data.pk'), os.path.join('data', 'airi_turtle_soup', 'data.pk.bak'))

timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
