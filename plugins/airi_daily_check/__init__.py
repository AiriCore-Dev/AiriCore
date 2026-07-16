import os
import gc
import re
import bz2
import sys
import json
import time
import math
import hmac
import httpx
import shutil
import pickle
import base64
import random
import hashlib
import nonebot
import asyncio
import requests
import importlib
import subprocess
import datetime

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from nonebot import get_driver, on_regex, on_startswith, on_fullmatch, require
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from utils.totp_2fa import totp_verify

from .base import cache

from .base import state
from .base.state import data, theme_extension, game_ans
from .base.constants import *
from .base.matchers import *
from .base.helpers import *
from .base.persistence import (
    load_json, save_to_json, daily_clear,
    reset_daily_challenge, save_data_backup, timings,
)
from . import handlers

driver = get_driver()
_2fa_key = getattr(driver.config, "_2fa_key", "")


@superuser_debug.handle()
async def _(bot: Bot, ev: MessageEvent):
    user_id, group_id = parse_session(ev)
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
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
    elif src == 'rdc':
        await reset_daily_challenge()
        res = '重置每日挑战：命令执行成功'
    else:
        try:
            try:
                res = eval(src)
            except:
                res = exec(src)
        except Exception as err:
            res = '出错了: ' + repr(err)
        else:
            res = '命令执行成功' if not res else str(res)
    await superuser_debug.finish(res, reply_message=True)


_roguelike = importlib.import_module(
    f"{__package__}.roguelike" if __package__ else "roguelike"
)
