from nonebot import get_driver

driver = get_driver()
unified_password = getattr(driver.config, "unified_password", "")
_2fa_key = getattr(driver.config, "_2fa_key", "")
notification_account = getattr(driver.config, "notification_account", "3630532026")

data = {}
email_list = []
server = None
