from nonebot import get_driver

driver = get_driver()
_2fa_key = getattr(driver.config, "_2fa_key", "")
notification_account = getattr(driver.config, "notification_account", "3630532026")

email_smtp_host = getattr(driver.config, "email_smtp_host", "gz-smtp.qcloudmail.com")
email_smtp_user = getattr(driver.config, "email_smtp_user", "airi@airi.asia")
email_smtp_password = getattr(driver.config, "email_smtp_password", "")
email_from_name = getattr(driver.config, "email_from_name", "Momoi Airi")
email_from_address = getattr(driver.config, "email_from_address", "airi@airi.asia")

data = {}
email_list = []
server = None
