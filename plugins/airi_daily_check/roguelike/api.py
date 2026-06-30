"""FastAPI app for the SEKAI roguelike — runs on its own port (default 22319).

Endpoints (all JSON; auth'd ones need `Authorization: Bearer <token>`):
    POST /api/auth/request           -> {code, ttl}                (no auth)
    GET  /api/auth/poll?code=        -> {bound, token?, qq?, nick?}(no auth)
    GET  /api/me                     -> {qq, nick, credits, avatar}
    POST /api/credits/spend  {amount,reason} -> {ok, credits}
    POST /api/credits/grant  {amount,reason} -> {ok, credits}   (结算返还)
    POST /api/sekai/score    {date,score}    -> {ok, best}
    GET  /api/sekai/board?date=      -> {date, rows:[{nick,qq,score}]}   (no auth)
    POST /api/sekai/activity/score {id,score} -> {ok, id, best}
    GET  /api/sekai/activity/board?id=  -> {id, rows:[{nick,qq,score}]}  (no auth)
    GET  /api/health                 -> {ok}

The credit pool IS the 签到积分 (`data[qq]['credits']`) — fully shared with the
QQ bot. Writes mutate the live dict; the parent plugin's periodic + shutdown
pickle jobs persist them.
"""

import math
import json
import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import auth, store

# 结算返还的硬上限：防止前端被篡改后注入天量积分。合法单局最高约 1020（满通+结余），留足余量。
GRANT_CAP = 10000

# 每日SEKAI可挑战次数（服务端权威，防跨设备/清缓存刷量）。
SEKAI_DAILY_LIMIT = 3

# 对局存档 blob 的大小上限（序列化后字节数）。正常对局 JSON 约几 KB，留足余量并防注入撑爆内存。
RUN_BLOB_MAX = 256 * 1024

app = FastAPI(title="SEKAI Roguelike API", docs_url=None, redoc_url=None)

# 网页与API不同源（网页域名 vs www.airi.asia:22319），需放开 CORS。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _auth_qq(authorization: str) -> str:
    """Extract & verify the QQ from a Bearer token, or raise 401."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    qq = auth.verify_token(token)
    if not qq:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return qq


def _mask_qq(qq: str) -> str:
    """Privacy mask for the public board: 12****89."""
    if len(qq) <= 4:
        return qq[:1] + "*" * (len(qq) - 1)
    return qq[:2] + "*" * (len(qq) - 4) + qq[-2:]


def _today_str() -> str:
    n = datetime.datetime.now()
    return f"{n.year}-{n.month:02d}-{n.day:02d}"


# --- request bodies ---------------------------------------------------------
class SpendBody(BaseModel):
    amount: int
    reason: str = ""


class GrantBody(BaseModel):
    amount: int
    reason: str = ""


class ScoreBody(BaseModel):
    date: str
    score: int


class ClaimBody(BaseModel):
    date: str


class ActScoreBody(BaseModel):
    # 活动榜分数上报：id 为活动标识（与前端 activities.js 的 act.id 一致）。
    id: str
    score: int


class RunBody(BaseModel):
    rev: int = 0
    # run 为对局存档对象；null 表示「当前无对局」（结算/放弃后清档）。
    run: dict | None = None


# --- auth -------------------------------------------------------------------
@app.post("/api/auth/request")
async def auth_request():
    code = auth.new_code()
    return {"code": code, "ttl": auth.CODE_TTL}


@app.get("/api/auth/poll")
async def auth_poll(code: str):
    res = auth.poll_code(code)
    if res is None:
        return {"bound": False}
    qq, nick = res
    store.ensure_account(qq)              # 首次登录即建号（与签到一致的新账户）
    acc = store.get_account(qq)
    acc["web_nick"] = nick
    token = auth.issue_token(qq)
    return {"bound": True, "token": token, "qq": qq, "nick": nick,
            "credits": int(acc.get("credits", 0))}


# --- account ----------------------------------------------------------------
@app.get("/api/me")
async def me(authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    acc = store.ensure_account(qq)
    today = _today_str()
    started = acc.get("sekai_started", {})
    run_rec = acc.get("sekai_run", {}) or {}
    used_today = int(started.get(today, 0))
    return {
        "qq": qq,
        "nick": acc.get("web_nick") or qq,
        "credits": int(acc.get("credits", 0)),
        "avatar": f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100",
        "daily_date": today,
        # daily_started 兼容旧前端：达到上限即视为"今日已用尽"。
        "daily_started": used_today >= SEKAI_DAILY_LIMIT,
        "daily_used": used_today,
        "daily_limit": SEKAI_DAILY_LIMIT,
        # 对局存档版本（前端据此判断服务端是否有更新的对局，无需每次拉全量）。
        "run_rev": int(run_rec.get("rev", 0)),
        "has_run": run_rec.get("run") is not None,
    }


@app.post("/api/credits/spend")
async def credits_spend(body: SpendBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    amount = int(body.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须为正")
    acc = store.ensure_account(qq)
    cur = int(acc.get("credits", 0))
    if cur < amount:                       # 余额二次校验，防并发/篡改超扣
        return JSONResponse(status_code=402,
                            content={"ok": False, "credits": cur, "detail": "积分不足"})
    acc["credits"] = cur - amount
    return {"ok": True, "credits": acc["credits"]}


@app.post("/api/credits/grant")
async def credits_grant(body: GrantBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    amount = int(body.amount)
    if amount < 0:
        raise HTTPException(status_code=400, detail="金额不能为负")
    amount = min(amount, GRANT_CAP)        # 封顶，防注入
    acc = store.ensure_account(qq)
    acc["credits"] = int(acc.get("credits", 0)) + amount
    return {"ok": True, "credits": acc["credits"]}


# --- daily SEKAI score / board ----------------------------------------------
@app.post("/api/sekai/claim")
async def sekai_claim(body: ClaimBody, authorization: str = Header(default="")):
    """原子领取一次今日每日资格：服务端是唯一权威，每日至多 SEKAI_DAILY_LIMIT 次。
    已用尽则返回 ok=False（前端据此置灰/提示今日已用尽）。"""
    qq = _auth_qq(authorization)
    date = body.date.strip()[:10]
    if not date:
        raise HTTPException(status_code=400, detail="缺少日期")
    acc = store.ensure_account(qq)
    started = acc.setdefault("sekai_started", {})
    used = int(started.get(date, 0))
    best = int(acc.get("sekai_daily", {}).get(date, 0))
    if used >= SEKAI_DAILY_LIMIT:
        return {"ok": False, "started": True, "used": used,
                "limit": SEKAI_DAILY_LIMIT, "best": best}
    started[date] = used + 1
    return {"ok": True, "started": True, "used": used + 1,
            "limit": SEKAI_DAILY_LIMIT, "best": best}


@app.post("/api/sekai/score")
async def sekai_score(body: ScoreBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    score = max(0, int(body.score))
    date = body.date.strip()[:10]
    if not date:
        raise HTTPException(status_code=400, detail="缺少日期")
    acc = store.ensure_account(qq)
    daily = acc.setdefault("sekai_daily", {})
    daily[date] = max(int(daily.get(date, 0)), score)
    return {"ok": True, "best": daily[date]}


@app.get("/api/sekai/board")
async def sekai_board(date: str, limit: int = 20):
    date = date.strip()[:10]
    limit = max(1, min(100, int(limit)))
    rows = []
    for qq, acc in store.get_data().items():
        if not isinstance(acc, dict):
            continue
        sc = acc.get("sekai_daily", {})
        if isinstance(sc, dict) and date in sc and sc[date] > 0:
            rows.append({
                "nick": acc.get("web_nick") or _mask_qq(qq),
                "qq": _mask_qq(qq),
                "score": int(sc[date]),
            })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return {"date": date, "rows": rows[:limit]}


# --- activity score / board (per-activity all-server leaderboard) ------------
# 活动榜与每日榜相互独立：按活动 id 分别排行，每个账号只记该活动的「历史最高分」。
# 存储结构：acc["sekai_activity"] = {<activity_id>: <best_score:int>, ...}
# 活动 id 长度上限，防异常超长键撑爆存储。
ACTIVITY_ID_MAX = 64


@app.post("/api/sekai/activity/score")
async def sekai_activity_score(body: ActScoreBody, authorization: str = Header(default="")):
    """上报某活动本局分数；服务端按活动 id 取该账号历史最高分。"""
    qq = _auth_qq(authorization)
    aid = body.id.strip()[:ACTIVITY_ID_MAX]
    if not aid:
        raise HTTPException(status_code=400, detail="缺少活动 id")
    score = max(0, int(body.score))
    acc = store.ensure_account(qq)
    act = acc.setdefault("sekai_activity", {})
    act[aid] = max(int(act.get(aid, 0)), score)
    return {"ok": True, "id": aid, "best": act[aid]}


@app.get("/api/sekai/activity/board")
async def sekai_activity_board(id: str, limit: int = 20):
    """拉取某活动的全服排行榜（按历史最高分降序）。无需登录。"""
    aid = id.strip()[:ACTIVITY_ID_MAX]
    if not aid:
        raise HTTPException(status_code=400, detail="缺少活动 id")
    limit = max(1, min(100, int(limit)))
    rows = []
    for qq, acc in store.get_data().items():
        if not isinstance(acc, dict):
            continue
        sc = acc.get("sekai_activity", {})
        if isinstance(sc, dict) and aid in sc and sc[aid] > 0:
            rows.append({
                "nick": acc.get("web_nick") or _mask_qq(qq),
                "qq": _mask_qq(qq),
                "score": int(sc[aid]),
            })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return {"id": aid, "rows": rows[:limit]}


# --- in-progress run save (cross-device sync) -------------------------------
@app.get("/api/sekai/load")
async def sekai_load(authorization: str = Header(default="")):
    """拉取账号上进行中的对局存档。返回 {rev, run}（run 可能为 null = 无对局）。
    服务端是跨设备同步的权威来源。"""
    qq = _auth_qq(authorization)
    acc = store.ensure_account(qq)
    rec = acc.get("sekai_run", {}) or {}
    return {"rev": int(rec.get("rev", 0)), "run": rec.get("run")}


@app.post("/api/sekai/save")
async def sekai_save(body: RunBody, authorization: str = Header(default="")):
    """保存进行中的对局存档（last-write-wins，按客户端 rev 递增）。
    rev 用于丢弃迟到的旧写入：仅当 body.rev >= 已存 rev 时才落库。
    run 为 null 表示清档（结算/放弃后调用）。"""
    qq = _auth_qq(authorization)
    rev = int(body.rev)
    run = body.run

    # 大小校验：拒绝异常巨大的 blob，防注入撑爆内存/pickle。
    if run is not None:
        try:
            size = len(json.dumps(run, ensure_ascii=False))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="对局数据无法序列化")
        if size > RUN_BLOB_MAX:
            raise HTTPException(status_code=413, detail="对局数据过大")

    acc = store.ensure_account(qq)
    rec = acc.get("sekai_run")
    if not isinstance(rec, dict):
        rec = {}
        acc["sekai_run"] = rec
    cur_rev = int(rec.get("rev", 0))
    if rev < cur_rev:
        # 迟到的旧写入：忽略，回报当前权威版本，客户端据此自我纠正。
        return {"ok": False, "stale": True, "rev": cur_rev}
    rec["rev"] = rev
    rec["run"] = run
    return {"ok": True, "rev": rev}


@app.get("/api/health")
async def health():
    return {"ok": True}
