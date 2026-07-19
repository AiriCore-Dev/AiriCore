import os
import pickle
import smtplib
import asyncio
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from nonebot import require
from nonebot.log import logger

from . import state
from .state import driver, email_smtp_host, email_smtp_user, email_smtp_password, email_from_name, email_from_address

timings = require("nonebot_plugin_apscheduler").scheduler

DATA_PATH = os.path.join("data", "airi_market", "data.pk")


@driver.on_startup
async def load_data():
    try:
        with open(DATA_PATH, "rb") as f:
            loaded = pickle.load(f)
        state.data.clear()
        state.data.update(loaded)
    except Exception:
        os.makedirs(os.path.join("data", "airi_market"), exist_ok=True)
        await save_data()
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


async def save_data():
    os.makedirs(os.path.join("data", "airi_market"), exist_ok=True)
    with open(DATA_PATH, "wb") as f:
        pickle.dump(dict(state.data), f)


def _build_msg(mail):
    if len(mail) >= 4 and mail[3]:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
        msg["To"] = Header(mail[0])
        msg["Subject"] = Header(mail[1], "utf-8")
        msg.attach(MIMEText(mail[2], "plain", "utf-8"))
        msg.attach(MIMEText(mail[3], "html", "utf-8"))
    else:
        msg = MIMEText(mail[2], "plain", "utf-8")
        msg["From"] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
        msg["To"] = Header(mail[0])
        msg["Subject"] = Header(mail[1], "utf-8")
    return msg


def _flush_email_queue_sync(mails):
    if _is_throttled():
        return []
    try:
        sev = smtplib.SMTP_SSL(email_smtp_host)
        sev.login(email_smtp_user, email_smtp_password)
        sent = []
        for mail in mails:
            if _is_throttled():
                break
            try:
                msg = _build_msg(mail)
                sev.sendmail(email_from_address, mail[0], msg.as_string())
                sent.append(mail)
            except smtplib.SMTPResponseException as e:
                err_msg = str(e)
                if "550" in err_msg and "frequency" in err_msg.lower():
                    _set_throttle()
                    break
            except Exception:
                pass
        sev.quit()
        return sent
    except Exception as e:
        logger.warning(f"airi_market flush_email_queue failed: {e}")
        return []


async def flush_email_queue():
    if not state.email_list:
        return
    mails = list(state.email_list)
    loop = asyncio.get_event_loop()
    sent = await loop.run_in_executor(None, _flush_email_queue_sync, mails)
    for mail in sent:
        try:
            state.email_list.remove(mail)
        except ValueError:
            pass


def _is_throttled():
    t = state.data.get("throttled_until")
    return t is not None and datetime.datetime.now() < t


def _set_throttle():
    resume_at = datetime.datetime.now() + datetime.timedelta(hours=6)
    state.data["throttled_until"] = resume_at
    logger.warning(f"airi_market 550 Domain frequency limited — 全部发信中止，将于 {resume_at.strftime('%Y-%m-%d %H:%M:%S')} 后重试")


def _send_single_sync(dest, subject, plain, html_body):
    if _is_throttled():
        return "throttled"
    try:
        sev = smtplib.SMTP_SSL(email_smtp_host)
        sev.login(email_smtp_user, email_smtp_password)
        mail = [dest, subject, plain, html_body]
        msg = _build_msg(mail)
        sev.sendmail(email_from_address, dest, msg.as_string())
        sev.quit()
        return True
    except smtplib.SMTPResponseException as e:
        err_msg = str(e)
        if "550" in err_msg and "frequency" in err_msg.lower():
            _set_throttle()
            return "throttled"
        logger.warning(f"airi_market _send_single failed to {dest}: {e}")
        return False
    except Exception as e:
        logger.warning(f"airi_market _send_single failed to {dest}: {e}")
        return False


async def _send_single(dest, subject, plain, html_body):
    if _is_throttled():
        return "throttled"
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send_single_sync, dest, subject, plain, html_body)


async def market_tick():
    now = datetime.datetime.now()

    throttled_until = state.data.get("throttled_until")
    if throttled_until is not None:
        if now < throttled_until:
            return
        state.data.pop("throttled_until", None)
        logger.info("airi_market 解除限流，恢复发信")

    pending = state.data.get("pending_sends", [])
    if pending:
        item = pending.pop(0)
        if isinstance(item, dict):
            result = await _send_single(item["dest"], item["subject"], item["plain"], item["html"])
        else:
            result = await _send_single(*item)
        if result is True:
            if isinstance(item, dict) and item.get("bot_qq"):
                state.data.setdefault("bot_notified", []).append(item["bot_qq"])
            logger.info(f"airi_market: pending send to {item['dest'] if isinstance(item, dict) else item[0]} 重发成功")
        else:
            pending.insert(0, item)
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

    total_minutes = (end_h - start_h) * 60
    elapsed_minutes = (now.hour - start_h) * 60 + now.minute
    target_sent = int(elapsed_minutes / total_minutes * daily_limit)

    if sent_today >= target_sent:
        return

    for campaign_name, campaign in list(state.data.get("campaigns", {}).items()):
        if campaign.get("status") != "running":
            continue
        queue = campaign.get("queue", [])
        if not queue:
            campaign["status"] = "done"
            logger.info(f"airi_market campaign '{campaign_name}' completed")
            continue

        qq = queue.pop(0)
        campaign["sent"] = campaign.get("sent", 0) + 1
        state.data["sent_today"] = sent_today + 1

        try:
            from .helpers import parse_article, make_token
            from .email_template import render_marketing_email
            article_info = parse_article(campaign_name)
            token = make_token(qq)
            unsub_url = f"https://{state.market_domain}:{state.market_port}/unsubscribe?token={token}"
            subject, plain, html_body = render_marketing_email(article_info, qq, unsub_url)
            result = await _send_single(f"{qq}@qq.com", subject, plain, html_body)
            if result in ("throttled", False):
                queue.insert(0, qq)
                campaign["sent"] = max(0, campaign["sent"] - 1)
                state.data["sent_today"] = max(0, state.data["sent_today"] - 1)
            else:
                sent_list = state.data.setdefault("article_sent", {}).setdefault(campaign_name, [])
                if qq not in sent_list:
                    sent_list.append(qq)
        except Exception as e:
            logger.warning(f"airi_market tick error for qq={qq}: {e}")
            queue.insert(0, qq)
            campaign["sent"] = max(0, campaign["sent"] - 1)
            state.data["sent_today"] = max(0, state.data["sent_today"] - 1)

        await save_data()
        return

    await save_data()


timings.add_job(market_tick, "cron", minute="*", misfire_grace_time=60, coalesce=True)
timings.add_job(save_data, "interval", minutes=5, misfire_grace_time=300, coalesce=True)
