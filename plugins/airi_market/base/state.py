import os
import secrets
from nonebot import get_driver

driver = get_driver()

_2fa_key = getattr(driver.config, "_2fa_key", "")

market_domain = getattr(driver.config, "market_domain", "ws.airi.asia")
market_port = int(getattr(driver.config, "market_port", 22320))
market_daily_limit = int(getattr(driver.config, "market_daily_limit", 200))
market_send_start_hour = int(getattr(driver.config, "market_send_start_hour", 9))
market_send_end_hour = int(getattr(driver.config, "market_send_end_hour", 17))
market_bind_host = str(getattr(driver.config, "market_bind_host", "") or "").strip()
market_allow_insecure_http = bool(getattr(driver.config, "market_allow_insecure_http", False))

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

POSTS_DIR = os.path.join(_PLUGIN_DIR, "posts")
TEMPLATES_DIR = os.path.join(_PLUGIN_DIR, "templates")
SSL_CERT = os.path.join(_ROOT_DIR, "ssl", "fullchain.pem")
SSL_KEY = os.path.join(_ROOT_DIR, "ssl", "privkey.key")

data = {
    "unsubscribed": [],
    "campaigns": {},
    "bot_notified": [],
    "token_secret": secrets.token_hex(32),
    "sent_today": 0,
    "sent_date": "",
}

email_list = []
_web_runner = None
