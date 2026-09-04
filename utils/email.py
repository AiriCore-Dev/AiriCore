import asyncio
import datetime
from pathlib import Path
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from nonebot import get_driver
from nonebot.log import logger

SMTP_TIMEOUT = 30
THROTTLE_HOURS = 6
_conf = None
_throttled_until = None
_on_throttle = None

_BASE_TEMPLATE = Path(__file__).resolve().parent / "templates" / "base.html"
_base_cache = None

def load_base():
    global _base_cache
    if _base_cache is None:
        _base_cache = _BASE_TEMPLATE.read_text(encoding="utf-8")
    return _base_cache

def _config():
    global _conf
    if _conf is None:
        cfg = get_driver().config
        _conf = {"host": str(getattr(cfg, "email_smtp_host", "") or "").strip(), "user": str(getattr(cfg, "email_smtp_user", "") or "").strip(), "password": str(getattr(cfg, "email_smtp_password", "") or ""), "from_name": str(getattr(cfg, "email_from_name", "") or "").strip(), "from_address": str(getattr(cfg, "email_from_address", "") or "").strip()}
    return _conf

def is_configured():
    conf = _config()
    return bool(conf["host"] and conf["user"] and conf["password"] and conf["from_address"])

def smtp_host():
    return _config()["host"]

def smtp_user():
    return _config()["user"]

def from_address():
    return _config()["from_address"]

def set_throttle_hook(callback):
    global _on_throttle
    _on_throttle = callback

def get_throttled_until():
    return _throttled_until

def set_throttled_until(value, notify=True):
    global _throttled_until
    _throttled_until = value
    if notify and _on_throttle is not None:
        try:
            _on_throttle(value)
        except Exception as e:
            logger.warning(f"mailer 限流回调失败: {e}")

def is_throttled():
    global _throttled_until
    if _throttled_until is None:
        return False
    if datetime.datetime.now() < _throttled_until:
        return True
    set_throttled_until(None)
    return False

def _set_throttle():
    resume_at = datetime.datetime.now() + datetime.timedelta(hours=THROTTLE_HOURS)
    set_throttled_until(resume_at)
    logger.warning(f"mailer 550 Domain frequency limited，将于 {resume_at.strftime('%Y-%m-%d %H:%M:%S')} 后重试")

def _is_frequency_limit(exc):
    text = str(exc)
    return "550" in text and "frequency" in text.lower()

def build_message(dest, subject, plain, html_body=None):
    conf = _config()
    sender = f"{Header(conf['from_name'], 'utf-8')} <{conf['from_address']}>" if conf["from_name"] else conf["from_address"]
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(plain or "", "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEText(plain or "", "plain", "utf-8")
    msg["From"] = sender
    msg["To"] = Header(dest)
    msg["Subject"] = Header(subject, "utf-8")
    return msg

def _connect():
    conf = _config()
    server = smtplib.SMTP_SSL(conf["host"], timeout=SMTP_TIMEOUT)
    server.login(conf["user"], conf["password"])
    return server

def send_batch_sync(items, tag="mailer"):
    if not is_configured():
        logger.warning(f"{tag} 邮件配置为空，已跳过发信")
        return [False] * len(items)
    if is_throttled():
        return ["throttled"] * len(items)
    try:
        server = _connect()
    except Exception as e:
        logger.warning(f"{tag} SMTP 连接失败: {e}")
        return [False] * len(items)
    conf = _config()
    results = []
    try:
        for item in items:
            dest, subject, plain = item[0], item[1], item[2]
            html_body = item[3] if len(item) >= 4 else None
            try:
                server.sendmail(conf["from_address"], dest, build_message(dest, subject, plain, html_body).as_string())
                results.append(True)
            except smtplib.SMTPResponseException as e:
                if _is_frequency_limit(e):
                    _set_throttle()
                    results.append("throttled")
                else:
                    logger.warning(f"{tag} 发信被拒 {dest}: {e}")
                    results.append(False)
            except Exception as e:
                logger.warning(f"{tag} 发信失败 {dest}: {e}")
                results.append(False)
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return results

def send_single_sync(dest, subject, plain, html_body=None, tag="mailer"):
    return send_batch_sync([(dest, subject, plain, html_body)], tag)[0]

async def send_batch(items, tag="mailer"):
    if not is_configured():
        return [False] * len(items)
    if is_throttled():
        return ["throttled"] * len(items)
    return await asyncio.to_thread(send_batch_sync, items, tag)

async def send_single(dest, subject, plain, html_body=None, tag="mailer"):
    if not is_configured():
        return False
    if is_throttled():
        return "throttled"
    return await asyncio.to_thread(send_single_sync, dest, subject, plain, html_body, tag)

async def probe():
    if not is_configured():
        return False, "SMTP 未配置"
    try:
        server = await asyncio.to_thread(_connect)
        await asyncio.to_thread(server.quit)
        return True, f"SMTP 连接正常（{smtp_host()} / {smtp_user()}）"
    except Exception as e:
        return False, f"SMTP 连接失败：{e}"

async def flush_queue(queue, tag="mailer"):
    if not queue:
        return 0, 0, ""
    mails = list(queue)
    results = await send_batch(mails, tag)
    sent = 0
    err = ""
    for mail, result in zip(mails, results):
        if result is True:
            sent += 1
            try:
                queue.remove(mail)
            except ValueError:
                pass
        elif result == "throttled":
            err = "发信被限流"
    if sent < len(mails) and not err:
        err = "部分邮件发送失败"
    return sent, len(mails), err
