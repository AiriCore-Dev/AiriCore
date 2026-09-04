import asyncio
import os
import gc
import shutil
import pickle
import tempfile
import datetime

import nonebot
from nonebot import get_driver, logger, require
from PIL import ImageDraw
from utils import credits

from . import state
from . import cache
from . import sudoku
from .constants import DATA_DIR, DATA_FILE, asset

timings = require("nonebot_plugin_apscheduler").scheduler
driver = get_driver()

CHALLENGE_FILE = os.path.join(DATA_DIR, 'challenge.pk')
_save_lock = asyncio.Lock()
_load_failed = False


def _today_str():
    nows = datetime.datetime.now()
    return '{:04d}-{:02d}-{:02d}'.format(nows.year, nows.month, nows.day)


def _try_load(path):
    with open(path, 'rb') as f:
        loaded = pickle.load(f)
    if not isinstance(loaded, dict):
        raise ValueError('存档结构异常')
    return loaded


@driver.on_startup
async def load_json():
    global _load_failed
    state.game_ans[:] = [0, '', '', '']
    os.makedirs(DATA_DIR, exist_ok=True)

    loaded = None
    if os.path.exists(DATA_FILE):
        try:
            loaded = _try_load(DATA_FILE)
        except Exception as e:
            logger.error(f"airi_daily_check 存档读取失败: {e}")
            bak = DATA_FILE + '.bak'
            if os.path.exists(bak):
                try:
                    loaded = _try_load(bak)
                    logger.warning("airi_daily_check 已从 .bak 备份恢复存档")
                except Exception as e2:
                    logger.error(f"airi_daily_check 备份也无法读取: {e2}")
            if loaded is None:
                try:
                    os.replace(DATA_FILE, DATA_FILE + '.corrupt')
                    logger.error(
                        "airi_daily_check 坏档已改名为 data.pk.corrupt，"
                        "本次运行不会写入存档以避免数据丢失，请人工处理后重启"
                    )
                except OSError:
                    pass
                _load_failed = True

    if loaded is not None:
        _load_failed = False
        state.data.clear()
        state.data.update(loaded)
        _backfill_last_check_time()
    elif not _load_failed:
        await save_to_json()

    if not _load_failed:
        await credits.migrate_legacy_accounts(state.data)

    await asyncio.to_thread(_restore_or_reset_challenge)
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
            os.path.exists(asset('resources', 'sudoku', f'sdk_diff_{i}.jpg'))
            for i in range(1, 4)
        )
        if saved.get('date') == _today_str() and images_exist:
            state.game_ans[:] = saved['answers']
            return
    except:
        pass
    reset_daily_challenge()


def _atomic_dump(path, obj):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.tmp-', suffix='.pk')
    try:
        with os.fdopen(fd, 'wb') as f:
            pickle.dump(obj, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@driver.on_shutdown
async def save_to_json():
    if _load_failed:
        logger.warning("airi_daily_check 存档读取失败过，已跳过写入以保护数据")
        return
    async with _save_lock:
        try:
            _atomic_dump(DATA_FILE, state.data)
        except Exception as e:
            logger.error(f"airi_daily_check 存档写入失败: {e}")
        cache.flush()
        await credits.flush()


def _has_savedata(user_data):
    if user_data.get('collections'):
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
            if await credits.get_balance(uid) <= 0:
                to_remove.append(uid)

    for uid in to_remove:
        state.data.pop(uid, None)

    if to_remove:
        logger.info(f"airi_daily_check: 清理 {len(to_remove)} 个90天不活跃的空账号（无存档数据）")

    await save_to_json()


def reset_daily_challenge():
    puzzles, answers = sudoku.generate_daily()
    state.game_ans[:] = answers

    font = cache.get_font(asset('resources', 'font.ttc'), 60)
    nows = datetime.datetime.now()
    nows = '{}-{}-{}'.format(nows.year, nows.month, nows.day)
    for i in range(1, 4):
        sdk_bg = cache.get_image_copy(asset('resources', 'sudoku', f'sdk_bg_{i}.png'))
        board = puzzles[i]
        for j in range(81):
            digit = board[j]
            if digit:
                x1 = 155 + j % 9 * 150
                y1 = 155 + j // 9 * 150
                numj = cache.get_image(asset('resources', 'sudoku', f'{digit}.png'))
                sdk_bg.paste(numj, (x1, y1), mask=numj.split()[3])
        draw = ImageDraw.Draw(sdk_bg)
        draw.text(xy=(50, 1560), text=nows, fill=(0, 0, 0), font=font)
        sdk_bg.convert('RGB').save(asset('resources', 'sudoku', f'sdk_diff_{i}.jpg'), format='JPEG', quality=95)

    try:
        _atomic_dump(CHALLENGE_FILE, {'date': _today_str(), 'answers': list(state.game_ans)})
    except Exception as e:
        logger.warning(f"airi_daily_check 每日挑战存档写入失败: {e}")


async def save_data_backup():
    await save_to_json()
    if _load_failed:
        return
    try:
        shutil.copyfile(DATA_FILE, DATA_FILE + '.bak')
    except Exception as e:
        logger.warning(f"airi_daily_check 存档备份失败: {e}")


async def midnight_job():
    await daily_clear()
    await asyncio.to_thread(reset_daily_challenge)


timings.add_job(midnight_job, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
