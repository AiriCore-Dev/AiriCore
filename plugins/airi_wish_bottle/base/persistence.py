import os
import shutil
import pickle
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from nonebot import require

from . import state
from .state import driver, unified_password

timings = require("nonebot_plugin_apscheduler").scheduler


async def email_login():
    try:
        state.server.connect()
    except:
        state.server = smtplib.SMTP_SSL("gz-smtp.qcloudmail.com")
        state.server.login('airi@airi.asia', unified_password)
        state.server.close()


@driver.on_startup
async def load_json():
    try:
        with open(os.path.join('data', 'airi_wish_bottle', 'data.pk'), 'rb') as f:
            loaded = pickle.load(f)
        state.data.clear()
        state.data.update(loaded)
    except:
        os.makedirs(os.path.join('data', 'airi_wish_bottle'))
        await save_to_json()


@driver.on_shutdown
async def save_to_json():
    with open(os.path.join('data', 'airi_wish_bottle', 'data.pk'), 'wb') as f:
        pickle.dump(state.data, f)
    if len(state.email_list):
        try:
            sev = smtplib.SMTP_SSL("gz-smtp.qcloudmail.com")
            sev.login('airi@airi.asia', unified_password)
            for mail in state.email_list:
                msg = MIMEText(mail[2], 'plain', 'utf-8')
                msg['From'] = f"{Header('Momoi Airi', 'utf-8')} <airi@airi.asia>"
                msg['To'] = Header(mail[0])
                msg['Subject'] = Header(mail[1])
                sev.sendmail('airi@airi.asia', mail[0], msg.as_string())
            sev.quit()
            del sev
            state.email_list = []
        except Exception as expt:
            return str(expt)


async def daily_clear():
    state.data["comments_daily"] = {}
    state.data["drop_daily"] = []
    await save_to_json()


async def save_data_backup():
    await save_to_json()
    shutil.copyfile(os.path.join('data', 'airi_wish_bottle', 'data.pk'), os.path.join('data', 'airi_wish_bottle', 'data.pk.bak'))


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
