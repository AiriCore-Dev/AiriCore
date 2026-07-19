import os
import secrets
from nonebot import get_driver

driver = get_driver()

email_smtp_host = getattr(driver.config, "email_smtp_host", "gz-smtp.qcloudmail.com")
email_smtp_user = getattr(driver.config, "email_smtp_user", "airi@airi.asia")
email_smtp_password = getattr(driver.config, "email_smtp_password", "")
email_from_name = getattr(driver.config, "email_from_name", "Momoi Airi")
email_from_address = getattr(driver.config, "email_from_address", "airi@airi.asia")
_2fa_key = getattr(driver.config, "_2fa_key", "")

market_domain = getattr(driver.config, "market_domain", "ws.airi.asia")
market_port = int(getattr(driver.config, "market_port", 22320))
market_daily_limit = int(getattr(driver.config, "market_daily_limit", 200))
market_send_start_hour = int(getattr(driver.config, "market_send_start_hour", 9))
market_send_end_hour = int(getattr(driver.config, "market_send_end_hour", 17))

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
