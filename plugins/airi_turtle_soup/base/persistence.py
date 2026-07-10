import os
import pickle
import shutil
from nonebot import get_driver, require
from . import state

driver = get_driver()
timings = require("nonebot_plugin_apscheduler").scheduler

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
    for i in state.data['group']:
        state.data['group'][i]['times'] = 0
    await save_to_json()

async def save_data_backup():
    await save_to_json()
    shutil.copyfile(os.path.join('data', 'airi_turtle_soup', 'data.pk'), os.path.join('data', 'airi_turtle_soup', 'data.pk.bak'))

timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
