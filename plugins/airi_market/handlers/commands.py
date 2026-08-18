import datetime
import traceback

import nonebot
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.log import logger
from utils.totp_2fa import totp_verify
from utils import email as mailer

from ..base import state
from ..base.matchers import airimarket, airimarketlist, airimarkettest, airimarketcancel, airimarketboost, airimarketsdebug
from ..base.helpers import list_articles, get_all_users, parse_article, make_token, parse_market_args
from ..base.persistence import save_data
from ..base.email_template import render_marketing_email


@airimarket.handle()
async def handle_airimarket(bot: Bot, ev: MessageEvent):
    text = ev.get_plaintext().strip()
    parts = text.split(None, 1)
    if len(parts) < 2:
        articles = list_articles()
        tip = "可用文章：\n" + "\n".join(articles) if articles else "暂无可用文章"
        await airimarket.finish(f"用法：airimarket [文章名称] [--group g1,g2] [--bot b1,b2]\n{tip}")

    article_name, group_ids, bot_ids = parse_market_args(parts[1])

    articles = list_articles()
    if article_name not in articles:
        tip = "可用文章：\n" + "\n".join(articles) if articles else "暂无可用文章"
        await airimarket.finish(f"文章 '{article_name}' 不存在\n{tip}")

    existing = state.data.get("campaigns", {}).get(article_name)
    if existing and existing.get("status") == "running":
        sent = existing.get("sent", 0)
        total = existing.get("total", 0)
        await airimarket.finish(
            f"文章 '{article_name}' 正在推送中\n进度：{sent}/{total}"
        )

    await airimarket.send("正在收集用户列表，请稍候...")

    try:
        article_info = parse_article(article_name)
    except Exception as e:
        await airimarket.finish(f"文章解析失败：{e}")

    bots = list(nonebot.get_bots().values())
    all_users = await get_all_users(bots, group_ids=group_ids, bot_ids=bot_ids)
    unsubscribed = set(state.data.get("unsubscribed", []))
    already_sent = set(state.data.get("article_sent", {}).get(article_name, []))
    targets = sorted(all_users - unsubscribed - already_sent)

    if not targets:
        await airimarket.finish("没有可推送的用户（无群成员或全部已退订）")

    state.data.setdefault("campaigns", {})[article_name] = {
        "article": article_name,
        "title": article_info["title"],
        "total": len(targets),
        "sent": 0,
        "queue": targets,
        "status": "running",
        "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    await save_data()

    filter_notes = []
    if bot_ids:
        filter_notes.append(f"Bot 过滤：{', '.join(sorted(bot_ids))}")
    if group_ids:
        filter_notes.append(f"群组过滤：{', '.join(sorted(group_ids))}")
    filter_line = ("\n" + "\n".join(filter_notes)) if filter_notes else ""

    await airimarket.finish(
        f"推送任务已创建：{article_name}\n"
        f"标题：{article_info['title']}\n"
        f"目标用户：{len(targets)} 人（已排除 {len(unsubscribed)} 人退订、{len(already_sent)} 人已发过）"
        f"{filter_line}\n"
        f"每日上限：{state.market_daily_limit} 封\n"
        f"发送时段：{state.market_send_start_hour}:00 - {state.market_send_end_hour}:00"
    )


@airimarkettest.handle()
async def handle_airimarkettest(bot: Bot, ev: MessageEvent):
    text = ev.get_plaintext().strip()
    parts = text.split(None, 2)
    if len(parts) < 3:
        await airimarkettest.finish("用法：airimarkettest [文章名称] [邮箱]")

    article_name = parts[1].strip()
    dest_email = parts[2].strip()

    articles = list_articles()
    if article_name not in articles:
        tip = "可用文章：\n" + "\n".join(articles) if articles else "暂无可用文章"
        await airimarkettest.finish(f"文章 '{article_name}' 不存在\n{tip}")

    try:
        article_info = parse_article(article_name)
    except Exception as e:
        await airimarkettest.finish(f"文章解析失败：{e}")

    token = make_token("test")
    unsub_url = f"{state.market_scheme}://{state.market_domain}:{state.market_port}/unsubscribe?token={token}"
    subject, plain, html_body = render_marketing_email(article_info, "test", unsub_url)

    from ..base.persistence import _send_single
    result = await _send_single(dest_email, subject, plain, html_body)
    if result is True:
        await airimarkettest.finish(f"测试邮件已发送至 {dest_email}")
    elif result == "throttled":
        await airimarkettest.finish("当前发信受限（550），请稍后再试")
    else:
        await airimarkettest.finish(f"发送失败，请检查日志")


@airimarketlist.handle()
async def handle_airimarketlist(bot: Bot, ev: MessageEvent):
    campaigns = state.data.get("campaigns", {})
    if not campaigns:
        await airimarketlist.finish("当前没有推送任务")

    lines = ["当前推送任务列表："]
    for name, c in campaigns.items():
        total = c.get("total", 0)
        sent = c.get("sent", 0)
        status = c.get("status", "unknown")
        pct = f"{sent / total * 100:.1f}%" if total else "0%"
        status_label = {"running": "进行中", "done": "已完成", "cancelled": "已取消"}.get(status, status)
        lines.append(
            f"\n[{status_label}] {name}\n"
            f"  标题：{c.get('title', name)}\n"
            f"  进度：{sent}/{total}（{pct}）\n"
            f"  开始：{c.get('started_at', '未知')}"
        )

    today_sent = state.data.get("sent_today", 0)
    lines.append(f"\n今日已发：{today_sent}/{state.market_daily_limit}")
    await airimarketlist.finish("\n".join(lines))


@airimarketcancel.handle()
async def handle_airimarketcancel(bot: Bot, ev: MessageEvent):
    text = ev.get_plaintext().strip()
    parts = text.split(None, 1)
    if len(parts) < 2:
        await airimarketcancel.finish("用法：airimarketcancel [文章名称]")

    article_name = parts[1].strip()
    campaigns = state.data.get("campaigns", {})
    if article_name not in campaigns:
        await airimarketcancel.finish(f"未找到推送任务：{article_name}")

    campaign = campaigns[article_name]
    status = campaign.get("status", "unknown")
    if status != "running":
        status_label = {"done": "已完成", "cancelled": "已取消"}.get(status, status)
        await airimarketcancel.finish(f"任务 '{article_name}' 当前状态为「{status_label}」，无需取消")

    sent = campaign.get("sent", 0)
    total = campaign.get("total", 0)
    campaign["status"] = "cancelled"
    campaign["queue"] = []
    await save_data()

    await airimarketcancel.finish(
        f"已取消推送任务：{article_name}\n"
        f"已发送：{sent}/{total}"
    )


@airimarketboost.handle()
async def handle_airimarketboost(bot: Bot, ev: MessageEvent):
    text = ev.get_plaintext().strip()
    parts = text.split(None, 2)
    if len(parts) < 3:
        await airimarketboost.finish("用法：airimarketboost [文章名称] [数量]")

    article_name = parts[1].strip()
    try:
        count = int(parts[2].strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await airimarketboost.finish("数量必须为正整数")

    campaigns = state.data.get("campaigns", {})
    if article_name not in campaigns:
        await airimarketboost.finish(f"未找到推送任务：{article_name}")

    campaign = campaigns[article_name]
    if campaign.get("status") != "running":
        status_label = {"done": "已完成", "cancelled": "已取消"}.get(campaign.get("status", ""), campaign.get("status", ""))
        await airimarketboost.finish(f"任务 '{article_name}' 当前状态为「{status_label}」，无法加速")

    queue = campaign.get("queue", [])
    if not queue:
        campaign["status"] = "done"
        await save_data()
        await airimarketboost.finish(f"任务 '{article_name}' 队列已空，已标记为完成")

    actual = min(count, len(queue))
    await airimarketboost.send(f"开始立即推送 {actual} 封邮件，请稍候...")

    from ..base.helpers import parse_article, make_token
    from ..base.email_template import render_marketing_email
    from ..base.persistence import _send_single

    try:
        article_info = parse_article(article_name)
    except Exception as e:
        await airimarketboost.finish(f"文章解析失败：{e}")

    success = 0
    failed = 0
    throttled = False
    sent_today = state.data.get("sent_today", 0)
    requeue_tail = []

    for _ in range(actual):
        if not queue:
            break
        qq = queue.pop(0)
        try:
            token = make_token(qq)
            unsub_url = f"{state.market_scheme}://{state.market_domain}:{state.market_port}/unsubscribe?token={token}"
            subject, plain, html_body = render_marketing_email(article_info, qq, unsub_url)
            result = await _send_single(f"{qq}@qq.com", subject, plain, html_body)
            if result is True:
                campaign["sent"] = campaign.get("sent", 0) + 1
                sent_today += 1
                success += 1
                sent_list = state.data.setdefault("article_sent", {}).setdefault(article_name, [])
                if qq not in sent_list:
                    sent_list.append(qq)
            elif result == "throttled":
                queue.insert(0, qq)
                throttled = True
                break
            else:
                requeue_tail.append(qq)
                failed += 1
        except Exception as e:
            logger.warning(f"airi_market boost error for qq={qq}: {e}")
            requeue_tail.append(qq)
            failed += 1

    queue.extend(requeue_tail)
    state.data["sent_today"] = sent_today

    if not queue:
        campaign["status"] = "done"
        logger.info(f"airi_market campaign '{article_name}' completed via boost")

    await save_data()

    remaining = len(queue)
    if throttled:
        status_note = f"（已触发限流，中止推送，剩余队列：{remaining} 人）"
    elif campaign.get("status") == "done":
        status_note = "（队列已清空，任务完成）"
    else:
        status_note = f"（剩余队列：{remaining} 人）"
    await airimarketboost.finish(
        f"立即推送完成：{article_name}\n"
        f"成功：{success} 封　失败：{failed} 封\n"
        f"累计已发：{campaign.get('sent', 0)}/{campaign.get('total', 0)}{status_note}"
    )


@airimarketsdebug.handle()
async def handle_airimarketsdebug(bot: Bot, ev: MessageEvent):
    if not str(state._2fa_key or "").strip():
        await airimarketsdebug.finish("未配置 _2fa_key，调试通道已禁用")
    src = ev.get_plaintext()[6:].strip()
    while (tmpa := src.replace("  ", " ")) != src:
        src = tmpa
    user_2fa_digit = src[:6]
    if not totp_verify(state._2fa_key, user_2fa_digit):
        await airimarketsdebug.finish("2fa verification failed")
    src = src[6:].strip()
    if not src:
        await airimarketsdebug.finish("缺少要执行的表达式")
    if src == "save":
        await save_data()
        res = "存档：命令执行成功"
    elif src == "reset":
        state.data["sent_today"] = 0
        state.data["sent_date"] = ""
        await save_data()
        res = "重置今日发送计数：命令执行成功"
    elif src == "unthrottle":
        mailer.set_throttled_until(None)
        await save_data()
        res = "已清除限流状态：命令执行成功"
    else:
        awaited = src[:6] == "await "
        expr = src[6:].lstrip() if awaited else src
        _ns = {**globals(), "state": state, "save_data": save_data, "bot": bot, "ev": ev}
        try:
            try:
                res = eval(compile(expr, "<sdebug>", "eval"), _ns)
            except SyntaxError:
                res = exec(compile(expr, "<sdebug>", "exec"), _ns)
            if awaited and hasattr(res, "__await__"):
                res = await res
        except Exception:
            res = traceback.format_exc()
        else:
            res = "命令执行成功" if not res else str(res)
    await airimarketsdebug.finish(res, reply_message=True)
