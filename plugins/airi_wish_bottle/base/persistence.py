import os
import shutil
import pickle
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from nonebot import require

from . import state
from .state import driver, unified_password, email_smtp_host, email_smtp_user, email_smtp_password, email_from_name, email_from_address

timings = require("nonebot_plugin_apscheduler").scheduler


async def email_login():
    try:
        state.server.connect()
    except:
        state.server = smtplib.SMTP_SSL(email_smtp_host)
        state.server.login(email_smtp_user, email_smtp_password)
        state.server.close()


@driver.on_startup
async def load_json():
    try:
        with open(os.path.join('data', 'airi_wish_bottle', 'data.pk'), 'rb') as f:
            loaded = pickle.load(f)
        state.data.clear()
        state.data.update(loaded)
    except:
        os.makedirs(os.path.join('data', 'airi_wish_bottle'), exist_ok=True)
        await save_to_json()


@driver.on_shutdown
async def save_to_json():
    with open(os.path.join('data', 'airi_wish_bottle', 'data.pk'), 'wb') as f:
        pickle.dump(state.data, f)
    if len(state.email_list):
        try:
            from email.mime.multipart import MIMEMultipart
            sev = smtplib.SMTP_SSL(email_smtp_host)
            sev.login(email_smtp_user, email_smtp_password)
            for mail in state.email_list:
                if len(mail) >= 4 and mail[3]:
                    msg = MIMEMultipart('alternative')
                    msg['From'] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
                    msg['To'] = Header(mail[0])
                    msg['Subject'] = Header(mail[1])
                    msg.attach(MIMEText(mail[2], 'plain', 'utf-8'))
                    msg.attach(MIMEText(mail[3], 'html', 'utf-8'))
                else:
                    msg = MIMEText(mail[2], 'plain', 'utf-8')
                    msg['From'] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
                    msg['To'] = Header(mail[0])
                    msg['Subject'] = Header(mail[1])
                sev.sendmail(email_from_address, mail[0], msg.as_string())
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


async def flush_email_queue():
    if not state.email_list:
        return "邮件队列为空"
    count = len(state.email_list)
    try:
        from email.mime.multipart import MIMEMultipart
        sev = smtplib.SMTP_SSL(email_smtp_host)
        sev.login(email_smtp_user, email_smtp_password)
        for mail in state.email_list:
            if len(mail) >= 4 and mail[3]:
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
                msg['To'] = Header(mail[0])
                msg['Subject'] = Header(mail[1])
                msg.attach(MIMEText(mail[2], 'plain', 'utf-8'))
                msg.attach(MIMEText(mail[3], 'html', 'utf-8'))
            else:
                msg = MIMEText(mail[2], 'plain', 'utf-8')
                msg['From'] = f"{Header(email_from_name, 'utf-8')} <{email_from_address}>"
                msg['To'] = Header(mail[0])
                msg['Subject'] = Header(mail[1])
            sev.sendmail(email_from_address, mail[0], msg.as_string())
        sev.quit()
        del sev
        state.email_list = []
        return f"成功发送 {count} 封邮件"
    except Exception as expt:
        return f"发送失败（已发送部分，剩余 {len(state.email_list)} 封）：{str(expt)}"


timings.add_job(daily_clear, "cron", hour=0, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_data_backup, "cron", hour=23, minute=50, misfire_grace_time=3600, coalesce=True)
timings.add_job(save_to_json, "interval", minutes=5, misfire_grace_time=3600, coalesce=True)
