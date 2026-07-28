from nonebot import get_driver

driver = get_driver()
_2fa_key = str(getattr(driver.config, "_2fa_key", "") or "").strip()
notification_account = str(getattr(driver.config, "notification_account", "") or "").strip()

data = {}
email_list = []
