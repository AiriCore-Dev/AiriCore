import os
import gc
import random
import datetime
from io import BytesIO

from PIL import Image, ImageDraw
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent

from ..base import state
from ..base import cache
from ..base.constants import hidden_stickers, asset
from ..base.matchers import xinxi, shoucang, chouka, yincang17, theme_manage
from ..base.helpers import (
    parse_session, resting_guard, ensure_registered,
    download_avatar, get_sticker, make_250px_cached, generate_new_sticker,
    acquire_sticker, check_all_achiv, image_to_base64, localpath_to_base64,
)


@xinxi.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    user_id, group_id = parse_session(ev)
    await ensure_registered(shoucang, user_id)

    if os.path.exists(asset('info_bg', user_id)):
        bg_list = os.listdir(asset('info_bg', user_id))
        backg = Image.open(asset('info_bg', user_id, random.choice(bg_list))).convert('RGBA')
        xb, yb = backg.size
        backg = backg.resize((1414, 1414 * yb // xb) if yb > xb else (1322 * xb // yb, 1322))
        xb, yb = backg.size
        backg = backg.crop((0, yb // 2 - 661, 1413, yb // 2 + 661) if yb > xb else (xb // 2 - 707, 0, xb // 2 + 707, 1321))
    else:
        backg = cache.get_image_copy(asset('info_bg', 'default.png'))

    overlay_name = 'info_bg_1.png' if state.data[user_id]['check_times_daily'] else 'info_bg_0.png'
    backg_2 = cache.get_image(asset('utils', overlay_name))
    backg.paste(backg_2, (0, 0), mask=backg_2.split()[3])

    font_sakura = cache.get_font(asset('utils', 'sakura.ttf'), 36)
    font_louxing = cache.get_font(asset('utils', 'louxing.ttf'), 60)
    font_skc = cache.get_font(asset('utils', 'skc.ttf'), 48)
    draw = ImageDraw.Draw(backg)

    user_nick = ev.sender.card or ev.sender.nickname
    nick_len = draw.textlength(user_nick, font_skc)
    if nick_len > 302:
        user_nick = user_nick[:-1] + "…"
        nick_len = draw.textlength(user_nick, font_skc)
    while nick_len > 302:
        user_nick = user_nick[:-2] + "…"
        nick_len = draw.textlength(user_nick, font_skc)
    draw.text(xy=(92, 264), text=user_nick, fill=(0, 0, 0), font=font_skc)
    draw.text(xy=(92, 337), text='账户ID: ' + user_id, fill=(0, 0, 0), font=font_sakura)

    avater_bytes = await download_avatar(user_id)
    avater = Image.open(BytesIO(avater_bytes)).convert('RGBA').resize((200, 200))
    avater_mask = cache.get_image(asset('utils', 'avater_mask.png'))
    backg.paste(avater, (435, 192), mask=avater_mask.split()[3])

    draw.text(xy=(200 - draw.textlength((tmpdraw := str(state.data[user_id]["credits"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(520 - draw.textlength((tmpdraw := str(state.data[user_id]["checked_days"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(900 - draw.textlength((tmpdraw := str(200 - state.data[user_id]["receive_transfer_daily"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    draw.text(xy=(1220 - draw.textlength((tmpdraw := str(state.data[user_id]["reborn_times"])), font_louxing) // 2, 426), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    font_louxing = cache.get_font(asset('utils', 'louxing.ttf'), 48)
    draw.text(xy=(1046 - draw.textlength((tmpdraw := str(state.data[user_id]["theme"])), font_louxing) // 2, 266), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)

    clcp = cache.get_image(asset('utils', 'complete.png'))
    cordx = [0, 792, 988, 1183]
    for i in range(1, 4):
        if state.data[user_id]["daily_challenge"][i]:
            backg.paste(clcp, (cordx[i], 682), mask=clcp.split()[3])

    cl_n = sum(1 for i in range(101) if i in state.data[user_id]['collections'])
    cl_ur = sum(1 for i in range(101, 106) if i in state.data[user_id]['collections'])
    font_louxing = cache.get_font(asset('utils', 'louxing.ttf'), 100)
    draw.text(xy=(374 - draw.textlength((tmpdraw := str(cl_n).zfill(3) + '/100'), font_louxing) // 2, 710), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)
    font_louxing = cache.get_font(asset('utils', 'louxing.ttf'), 120)
    draw.text(xy=(374 - draw.textlength((tmpdraw := str(cl_ur) + '/5'), font_louxing) // 2, 972), text=tmpdraw, fill=(0, 0, 0), font=font_louxing)

    airi_head = cache.get_image(asset('utils', 'airi.png'))
    pgr = Image.new('RGBA', (564, 25), (255 if (rt := (100 - cl_n) * 255 // 50) > 255 else rt, 255 if (gt := cl_n * 255 // 50) > 255 else gt, 0, 0))
    pgr_mask = cache.get_image(asset('utils', 'pgr_mask.png'))
    pgr = pgr.crop((0, 0, 564 * cl_n // 100, 25))
    pgr_mask = pgr_mask.crop((0, 0, 564 * cl_n // 100, 25))
    backg.paste(pgr, (105, 890), mask=pgr_mask.split()[3])
    backg.paste(airi_head, (105 - 37 + 564 * cl_n // 100, 890 - 15), mask=airi_head.split()[3])

    pgr = Image.new('RGBA', (564, 25), (255 if (rt := (50 - cl_ur * 10) * 255 // 25) > 255 else rt, 255 if (gt := cl_n * 2550 // 25) > 255 else gt, 0, 0))
    pgr_mask = cache.get_image(asset('utils', 'pgr_mask.png'))
    pgr = pgr.crop((0, 0, 564 * cl_ur // 5, 25))
    pgr_mask = pgr_mask.crop((0, 0, 564 * cl_ur // 5, 25))
    backg.paste(pgr, (105, 1168), mask=pgr_mask.split()[3])
    backg.paste(airi_head, (105 - 37 + 564 * cl_ur // 5, 1168 - 15), mask=airi_head.split()[3])

    base64_img = image_to_base64(backg.convert('RGB'))
    await xinxi.send(MessageSegment.image(base64_img), reply_message=True)
    del backg, backg_2, font_louxing, font_sakura, font_skc, avater, avater_mask, draw, pgr, pgr_mask
    gc.collect()


@shoucang.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(shoucang, user_id)

    if src == '查看收藏':
        msg = []
        user_nick = ev.sender.card or ev.sender.nickname
        res = '账户昵称：{}\n账户id：{}\n'.format(user_nick, user_id)
        res += '今日已签到！' if state.data[user_id]['check_times_daily'] else '今日未签到'
        msg.append({"type": "node", "data": {"name": "基本信息", "uin": bot.self_id, "content": res}})

        backg = cache.get_image_copy(asset('stickers', state.data[user_id]['theme'], 'bg.png'))
        mask = cache.get_image(asset('stickers', state.data[user_id]['theme'], 'mask.png'))
        unk = cache.get_image(asset('utils', 'unknown.png'))
        unk_mask = unk.split()[3]
        draw = ImageDraw.Draw(backg)
        font = cache.get_font(asset('utils', 'font.ttc'), 48)
        draw.text(xy=(1843, 2783), text=user_nick if len(user_nick) <= 15 else user_nick[:15] + '...', fill=(0, 0, 0), font=font)
        draw.text(xy=(2046, 2841), text=user_id, fill=(0, 0, 0), font=font)
        draw.text(xy=(1816, 2898), text=str(datetime.datetime.now()), fill=(0, 0, 0), font=font)

        own_str = ['', '', '']
        for i in range(1, 101):
            x1 = ((i - 1) % 10) * 250
            y1 = int((i - 1) / 10 + 1) * 250
            if i in state.data[user_id]['collections']:
                stk = await get_sticker(i, user_id)
                sticker_img, sticker_mask = await make_250px_cached(stk)
                backg.paste(sticker_img, (x1, y1), mask=sticker_mask)
            else:
                backg.paste(unk, (x1, y1), mask=unk_mask)
        for i in range(101, 106):
            if i in state.data[user_id]['collections']:
                stk = await get_sticker(i, user_id)
                sticker_img, sticker_mask = await make_250px_cached(stk)
                x1 = ((i - 1) % 10) * 250
                y1 = int((i - 1) / 10 + 1) * 250
                backg.paste(sticker_img, (x1, y1), mask=sticker_mask)
                own_str[2] += '{}, '.format(i)
        own_str[2] = own_str[2][:-2]

        res_img = Image.new('RGBA', backg.size)
        res_img = Image.alpha_composite(res_img, backg)
        res_img = Image.alpha_composite(res_img, mask).convert('RGB')
        base64_img = image_to_base64(res_img)
        await shoucang.send(MessageSegment.image(base64_img), reply_message=True)
        del backg, mask, res_img, base64_img, font, draw
        gc.collect()
    else:
        try:
            query_id = src[4:]
            if query_id[:1] in ["品"]:
                query_id = query_id[1:]
            if query_id[-1:] in ["号"]:
                query_id = query_id[:-1]
            query_id = int(query_id)
            assert query_id in range(1, 106)
        except:
            await shoucang.finish('❌ 请输入正确的收藏编号！', reply_message=True)
        if query_id not in state.data[user_id]['collections']:
            await shoucang.finish('❌ 你还未拥有该收藏！', reply_message=True)
        stk = await get_sticker(query_id, user_id)
        stk_b64 = await localpath_to_base64(stk)
        msg = MessageSegment.text('📄第{}号收藏\n'.format(query_id)) + MessageSegment.image(stk_b64)
        await shoucang.finish(msg, reply_message=True)


@chouka.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(chouka, user_id)

    if src == '收藏抽卡':
        chouka_times = 1
    else:
        try:
            assert 11 > (chouka_times := int(src[4:])) > 0
        except:
            await chouka.finish('❌ 抽卡次数错误！\n抽卡次数可为：1-10次', reply_message=True)

    if state.data[user_id]['credits'] < chouka_times * 100:
        await chouka.finish('❌ 积分不够辣！>_<\n需要积分：{}\n现有积分：{}'.format(chouka_times * 100, state.data[user_id]['credits']), reply_message=True)
    state.data[user_id]['credits'] -= chouka_times * 100

    tot_new = tot_repeat = 0
    user_nick = ev.sender.card or ev.sender.nickname
    scck_bg_list = os.listdir(asset('utils', 'gacha'))
    backg = cache.get_image_copy(asset('utils', 'gacha', random.choice(scck_bg_list)))
    new_mask = cache.get_image(asset('utils', 'new_mask.png'))
    own_mask = cache.get_image(asset('utils', 'own_mask.png'))
    draw = ImageDraw.Draw(backg)
    font = cache.get_font(asset('utils', 'sakura.ttf'), 56)
    draw.text(xy=(380, 1110), text=user_nick if len(user_nick) <= 15 else user_nick[:15] + '...', fill=(0, 0, 0), font=font)
    draw.text(xy=(540, 1179), text=user_id, fill=(0, 0, 0), font=font)
    draw.text(xy=(351, 1248), text=str(datetime.datetime.now()), fill=(0, 0, 0), font=font)

    new_sticker = pas_sticker = 0
    for i in range(1, chouka_times + 1):
        rand_sticker = 17
        while rand_sticker in hidden_stickers:
            rand_sticker = random.randint(1, 100)
        if i == 10 and tot_repeat == 9:
            nonacq_tmp = [
                j for j in list(set(range(1, 101)) - set(hidden_stickers))
                if j not in state.data[user_id]['collections']
            ]
            if len(nonacq_tmp):
                rand_sticker = random.choice(nonacq_tmp)

        x1 = (i - 1) % 5 * 375 + 300
        y1 = (i - 1) // 5 * 375 + 300
        if acquire_sticker(user_id, rand_sticker):
            new_sticker = await generate_new_sticker(rand_sticker, user_id, 1)
            backg.paste(new_mask, (x1 - 20, y1 - 20), mask=new_mask.split()[3])
            backg.paste(new_sticker, (x1, y1))
            draw.text(xy=(x1 + 193, y1 - 13), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 187, y1 - 19), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 190, y1 - 16), text=f'{rand_sticker}'.zfill(2), fill=(255, 0, 0), font=font)
            tot_new += 1
        else:
            state.data[user_id]['credits'] += 50
            stk = await get_sticker(rand_sticker, user_id)
            pas_sticker, pas_mask = await make_250px_cached(stk, 1)
            backg.paste(own_mask, (x1 - 20, y1 - 20), mask=own_mask.split()[3])
            backg.paste(pas_sticker, (x1, y1))
            draw.text(xy=(x1 + 192, y1 - 13), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 187, y1 - 19), text=f'{rand_sticker}'.zfill(2), fill=(0, 0, 0), font=font)
            draw.text(xy=(x1 + 190, y1 - 16), text=f'{rand_sticker}'.zfill(2), fill=(255, 255, 0), font=font)
            tot_repeat += 1

    if state.data[user_id]["need_reborn"]:
        draw.text(xy=(216, 1045), text=f'你已经齐活了，快点重生吧！', fill=(0, 0, 0), font=font)
    elif tot_repeat != 10:
        draw.text(xy=(216, 1045), text=f'重复收藏共转化为{tot_repeat * 50}积分, 剩余积分: {state.data[user_id]["credits"]}', fill=(0, 0, 0), font=font)
    else:
        draw.text(xy=(216, 1045), text=f'怎么没NEW，是不是有隐藏收藏品……', fill=(0, 0, 0), font=font)

    base64_img = image_to_base64(backg.convert('RGB'))
    await chouka.send(MessageSegment.image(base64_img), reply_message=True)
    await check_all_achiv(user_id, bot, ev)
    del new_sticker, pas_sticker, base64_img, font, draw
    gc.collect()


@yincang17.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    user_id, group_id = parse_session(ev)
    await ensure_registered(yincang17, user_id)

    if acquire_sticker(user_id, 17):
        new_sticker = await generate_new_sticker(17, user_id)
        msg = MessageSegment.text(
            '好小子，怎么让你发现的？\n⭐ 隐藏成就解锁！\n🎖️ 获得第{}号隐藏收藏品\n🎉是NEW，好耶！🎉\n'.format(17)
        ) + MessageSegment.image(new_sticker)
    else:
        msg = MessageSegment.text('😡 拿过了就别再来辣！\nGet out!>_<')
    await yincang17.send(msg, reply_message=True)
    await check_all_achiv(user_id, bot, ev)
    gc.collect()


@theme_manage.handle()
async def _(bot: Bot, ev: MessageEvent):
    if await resting_guard():
        return
    user_id, group_id = parse_session(ev)
    src = str(ev.message)
    await ensure_registered(theme_manage, user_id)

    theme_list = sorted(os.listdir(asset('stickers')))
    if src == '收藏主题':
        res = '⭐ 当前收藏主题：{}\n\n🗒️ 所有主题：'.format(state.data[user_id]['theme'])
        for i in range(len(theme_list)):
            res += '\n{}. {}'.format(i + 1, theme_list[i])
        await theme_manage.finish(res, reply_message=True)
    else:
        change_theme = src[4:].lstrip()
        if change_theme.isdigit() and int(change_theme) <= len(theme_list):
            change_theme = theme_list[int(change_theme) - 1]
        if change_theme not in theme_list:
            await theme_manage.finish('❌ 找不到该主题，请检查拼写！', reply_message=True)
        state.data[user_id]['theme'] = change_theme
        await theme_manage.send('✅ 主题更改成功！\n当前收藏主题：{}'.format(state.data[user_id]['theme']), reply_message=True)
