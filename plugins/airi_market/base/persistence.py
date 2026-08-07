import os
import pickle
import shutil
import asyncio
import datetime
import tempfile

from nonebot import require
from nonebot.log import logger

from utils import email as mailer

from . import state
from .state import driver

timings = require("nonebot_plugin_apscheduler").scheduler

DATA_DIR = os.path.join("data", "airi_market")
DATA_PATH = os.path.join(DATA_DIR, "data.pk")
MAIL_TAG = "airi_market"
PENDING_MAX_RETRY = 5
TICK_BATCH_MAX = 10
_load_failed = False
_save_lock = asyncio.Lock()


def _try_load(path):
    with open(path, "rb") as f:
        loaded = pickle.load(f)
    if not isinstance(loaded, dict):
        raise ValueError("存档结构异常")
    return loaded


@driver.on_startup
async def load_data():
    global _load_failed
    os.makedirs(DATA_DIR, exist_ok=True)

    loaded = None
    if os.path.exists(DATA_PATH):
        try:
            loaded = _try_load(DATA_PATH)
        except Exception as e:
            logger.error(f"airi_market 存档读取失败: {e}")
            bak = DATA_PATH + ".bak"
            if os.path.exists(bak):
                try:
                    loaded = _try_load(bak)
                    logger.warning("airi_market 已从 .bak 备份恢复存档")
                except Exception as e2:
                    logger.error(f"airi_market 备份也无法读取: {e2}")
            if loaded is None:
                try:
                    os.replace(DATA_PATH, DATA_PATH + ".corrupt")
                    logger.error(
                        "airi_market 坏档已改名为 data.pk.corrupt，本次运行不再写入存档，"
                        "请人工处理后重启（退订名单可能受影响）"
                    )
                except OSError:
                    pass
                _load_failed = True

    if loaded is not None:
        state.data.clear()
        state.data.update(loaded)
    elif not _load_failed:
        await save_data()

    _restore_throttle()

    from ..web.server import start_server
    await start_server()


@driver.on_shutdown
async def on_shutdown():
    from . import cache as _cache
    _cache.flush()
    await save_data()
    await flush_email_queue()
    if state._web_runner is not None:
        try:
            await state._web_runner.cleanup()
        except Exception:
            pass


_CAMPAIGN_KEEP_DAYS = 90


def _prune_state():
    campaigns = state.data.get("campaigns")
    if isinstance(campaigns, dict) and len(campaigns) > 200:
        done = [
            (name, c) for name, c in campaigns.items()
            if isinstance(c, dict) and c.get("status") == "done"
        ]
        done.sort(key=lambda kv: kv[1].get("finished_at") or kv[1].get("started_at") or 0)
        for name, _ in done[: len(campaigns) - 200]:
            campaigns.pop(name, None)

async def save_data():
    if _load_failed:
        return
    async with _save_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        _prune_state()
        snapshot = dict(state.data)
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix=".tmp-", suffix=".pk")
        try:
            with os.fdopen(fd, "wb") as f:
                pickle.dump(snapshot, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, DATA_PATH)
        except Exception as e:
            logger.error(f"airi_market 存档写入失败: {e}")
            try:
                os.unlink(tmp)
            except OSError:
                pass


async def backup_data():
    await save_data()
    if _load_failed or not os.path.exists(DATA_PATH):
        return
    try:
        shutil.copyfile(DATA_PATH, DATA_PATH + ".bak")
    except Exception as e:
        logger.warning(f"airi_market 存档备份失败: {e}")


async def flush_email_queue():
    await mailer.flush_queue(state.email_list, MAIL_TAG)


def _sync_throttle_to_state(value):
    if value is None:
        state.data.pop("throttled_until", None)
    else:
        state.data["throttled_until"] = value


def _is_throttled():
    return mailer.is_throttled()


def _restore_throttle():
    mailer.set_throttle_hook(_sync_throttle_to_state)
    saved = state.data.get("throttled_until")
    if saved is not None:
        mailer.set_throttled_until(saved, notify=False)


async def _send_batch(items):
    return await mailer.send_batch(items, MAIL_TAG)


async def _send_single(dest, subject, plain, html_body):
    return await mailer.send_single(dest, subject, plain, html_body, MAIL_TAG)


async def market_tick():
    now = datetime.datetime.now()

    if mailer.is_throttled():
        return

    pending = state.data.get("pending_sends", [])
    if pending:
        item = pending[0]
        dest = item["dest"] if isinstance(item, dict) else item[0]
        bot_qq = item.get("bot_qq") if isinstance(item, dict) else None
        if bot_qq:
            state.invite_inflight.add(bot_qq)
        try:
            if isinstance(item, dict):
                result = await _send_single(
                    item["dest"], item["subject"], item["plain"], item["html"]
                )
            else:
                result = await _send_single(*item)
        finally:
            if bot_qq:
                state.invite_inflight.discard(bot_qq)
        if result is True:
            pending.remove(item)
            if bot_qq:
                notified = state.data.setdefault("bot_notified", [])
                if bot_qq not in notified:
                    notified.append(bot_qq)
            logger.info(f"airi_market: pending send to {dest} 重发成功")
        elif result == "throttled":
            pass
        else:
            fails = (item.get("fails", 0) + 1) if isinstance(item, dict) else 1
            if isinstance(item, dict):
                item["fails"] = fails
            if fails >= PENDING_MAX_RETRY:
                pending.remove(item)
                logger.error(
                    f"airi_market: pending send to {dest} 连续失败 {fails} 次，已丢弃该条"
                )
            else:
                pending.remove(item)
                pending.append(item)
        await save_data()
        return

    today_str = now.strftime("%Y-%m-%d")

    if state.data.get("sent_date") != today_str:
        state.data["sent_date"] = today_str
        state.data["sent_today"] = 0

    start_h = state.market_send_start_hour
    end_h = state.market_send_end_hour

    if not (start_h <= now.hour < end_h):
        return

    daily_limit = state.market_daily_limit
    sent_today = state.data.get("sent_today", 0)
    if sent_today >= daily_limit:
        return

    total_minutes = max(1, (end_h - start_h) * 60)
    elapsed_minutes = (now.hour - start_h) * 60 + now.minute + 1
    target_sent = min(daily_limit, int(elapsed_minutes / total_minutes * daily_limit))

    if sent_today >= target_sent:
        return

    budget = min(TICK_BATCH_MAX, target_sent - sent_today, daily_limit - sent_today)
    if budget <= 0:
        return

    picked = []
    for campaign_name, campaign in list(state.data.get("campaigns", {}).items()):
        if len(picked) >= budget:
            break
        if campaign.get("status") != "running":
            continue
        queue = campaign.get("queue", [])
        if not queue:
            campaign["status"] = "done"
            campaign["finished_at"] = now.timestamp()
            logger.info(f"airi_market campaign '{campaign_name}' completed")
            continue
        while queue and len(picked) < budget:
            picked.append((campaign_name, campaign, queue.pop(0)))

    if not picked:
        await save_data()
        return

    from .helpers import parse_article, make_token
    from .email_template import render_marketing_email

    items = []
    valid = []
    for campaign_name, campaign, qq in picked:
        try:
            article_info = parse_article(campaign_name)
            token = make_token(qq)
            unsub_url = f"https://{state.market_domain}:{state.market_port}/unsubscribe?token={token}"
            subject, plain, html_body = render_marketing_email(article_info, qq, unsub_url)
        except Exception as e:
            logger.warning(f"airi_market 渲染邮件失败 campaign={campaign_name} qq={qq}: {e}")
            campaign.get("queue", []).insert(0, qq)
            continue
        items.append((f"{qq}@qq.com", subject, plain, html_body))
        valid.append((campaign_name, campaign, qq))

    if not items:
        await save_data()
        return

    results = await _send_batch(items)

    for (campaign_name, campaign, qq), result in zip(valid, results):
        if result is True:
            campaign["sent"] = campaign.get("sent", 0) + 1
            state.data["sent_today"] = state.data.get("sent_today", 0) + 1
            sent_list = state.data.setdefault("article_sent", {}).setdefault(campaign_name, [])
            if qq not in sent_list:
                sent_list.append(qq)
        else:
            campaign.setdefault("queue", []).insert(0, qq)

    await save_data()


timings.add_job(market_tick, "cron", minute="*", misfire_grace_time=60, coalesce=True)
timings.add_job(save_data, "interval", minutes=5, misfire_grace_time=300, coalesce=True)
timings.add_job(backup_data, "cron", hour=23, minute=45, misfire_grace_time=3600, coalesce=True)
