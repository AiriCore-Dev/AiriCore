import os
import gc
import re
import json
import time
import math
import base64
import random
import shutil
import pickle
import hashlib
import nonebot
import requests
import datetime
from io import BytesIO
from utils.totp_2fa import totp_verify
from nonebot import get_driver, on_regex, on_startswith, on_fullmatch, require
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from .base.state import driver, unified_password, _2fa_key, data, email_list
from .base import state
from .base.matchers import *
from .base.helpers import *
from .base.persistence import (
    email_login,
    load_json,
    save_to_json,
    daily_clear,
    save_data_backup,
    flush_email_queue,
    timings,
)
from . import handlers


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    global data
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        split_id = session_id.split("_")
        user_id = split_id[2]
        gruop_id = split_id[1]
    else:
        user_id = session_id
        gruop_id = None
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  "," ")) != src:
        src = tmpa
    user_2fa_digit = src[:6]
    if not totp_verify(_2fa_key, user_2fa_digit):
        await superuser_debug.finish('2fa verification failed')
    src = src[6:].strip()
    user_nick = ev.sender.card or ev.sender.nickname
    if src == 'reset':
        await daily_clear()
        res = '刷新一天：命令执行成功'
    elif src == 'save':
        await save_to_json()
        res = '存档：命令执行成功'
    elif src == 'backup':
        await save_data_backup()
        res = '备份：命令执行成功'
    elif src == 'load':
        await load_json()
        res = '读档：命令执行成功'
    elif src[:6] == 'await ':
        try:
            try: res = await eval(src[6:])
            except: res = await exec(src[6:])
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    elif src == 'email':
        await email_login()
        res = '登录邮箱：命令执行成功'
    elif src == 'sendemail':
        res = await flush_email_queue()
    else:
        try:
            try: res = eval(src)
            except: res = exec(src)
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message = True)
