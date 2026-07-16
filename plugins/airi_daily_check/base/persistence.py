import os
import gc
import shutil
import pickle
import datetime

import nonebot
from nonebot import get_driver, require
from PIL import Image, ImageDraw, ImageFont

from . import state
from . import cache
from . import sudoku
from .constants import DATA_DIR, DATA_FILE, asset

timings = require("nonebot_plugin_apscheduler").scheduler
driver = get_driver()

CHALLENGE_FILE = os.path.join(DATA_DIR, 'challenge.pk')


def _today_str():
    nows = datetime.datetime.now()
    return '{}-{}-{}'.format(nows.year, nows.month, nows.day)


@driver.on_startup
async def load_json():
    state.game_ans[:] = [0, '', '', '']
    try:
        with open(DATA_FILE, 'rb') as f:
            loaded = pickle.load(f)
        state.data.clear()
        state.data.update(loaded)
        _backfill_last_check_time()
    except:
        os.makedirs(DATA_DIR, exist_ok=True)
        await save_to_json()
    _restore_or_reset_challenge()
    gc.collect()


def _backfill_last_check_time():
    now_ts = datetime.datetime.now().timestamp()
    for uid in state.data.keys():
        if 'last_check_time' not in state.data[uid]:
            state.data[uid]['last_check_time'] = now_ts


def _restore_or_reset_challenge():
    try:
        with open(CHALLENGE_FILE, 'rb') as f:
            saved = pickle.load(f)
        images_exist = all(
            os.path.exists(asset('utils', 'sudoku', f'sdk_diff_{i}.jpg'))
            for i in range(1, 4)
        )
        if saved.get('date') == _today_str() and images_exist:
            state.game_ans[:] = saved['answers']
            return
    except:
        pass
    reset_daily_challenge()


@driver.on_shutdown
async def save_to_json():
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(state.data, f)
    cache.flush()
    gc.collect()


def _has_savedata(user_data):
    if user_data.get('collections'):
        return True
    if user_data.get('credits', 0) > 0:
        return True
    if user_data.get('checked_days', 0) > 0:
        return True
    if user_data.get('reborn_times', 0) > 0:
        return True
    if user_data.get('theme', 'airi_momo') != 'airi_momo':
        return True
    return False


async def daily_clear():
    should_clear = bool(nonebot.get_bots())
    now = datetime.datetime.now()
    inactive_cutoff = (now - datetime.timedelta(days=90)).timestamp()

    to_remove = []
    for uid in state.data.keys():
        user_data = state.data[uid]
        if not user_data['check_times_daily'] and should_clear:
            user_data['checked_days'] = 0
        user_data['check_times_daily'] = 0
        user_data['receive_transfer_daily'] = 0
        user_data['daily_challenge'] = [0, 0, 0, 0]
        user_data['jrys'] = 0

        last_check = user_data.get('last_check_time')
        if (
            last_check is not None
            and last_check < inactive_cutoff
            and not _has_savedata(user_data)
        ):
            to_remove.append(uid)

    for uid in to_remove:
        state.data.pop(uid, None)

    if to_remove:
        nonebot.logger.info(f"airi_daily_check: 清理 {len(to_remove)} 个90天不活跃的空账号（无存档数据）")

    await save_to_json()


def reset_daily_challenge():
    puzzles, answers = sudoku.generate_daily()
    state.game_ans[:] = answers

    font = ImageFont.truetype(font=asset('utils', 'font.ttc'), size=60)
    nows = datetime.datetime.now()
    nows = '{}-{}-{}'.format(nows.year, nows.month, nows.day)
    num_imgs = {}
    for i in range(1, 4):
        sdk_bg = Image.open(asset('utils', 'sudoku', f'sdk_bg_{i}.png')).convert('RGBA')
        board = puzzles[i]
        for j in range(81):
            digit = board[j]
            if digit:
                x1 = 155 + j % 9 * 150
                y1 = 155 + j // 9 * 150
                numj = num_imgs.get(digit)
                if numj is None:
                    numj = Image.open(asset('utils', 'sudoku', f'{digit}.png')).convert('RGBA')
                    num_imgs[digit] = numj
                sdk_bg.paste(numj, (x1, y1), mask=numj.split()[3])
        draw = ImageDraw.Draw(sdk_bg)
        draw.text(xy=(50, 1560), text=nows, fill=(0, 0, 0), font=font)
        sdk_bg.convert('RGB').save(asset('utils', 'sudoku', f'sdk_diff_{i}.jpg'), format='JPEG', quality=95)

    try:
        with open(CHALLENGE_FILE, 'wb') as f:
            pickle.dump({'date': _today_str(), 'answers': list(state.game_ans)}, f)
    except:
        pass


async def save_data_backup():
    await save_to_json()
    shutil.copyfile(DATA_FILE, DATA_FILE + '.bak')


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(reset_daily_challenge, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
