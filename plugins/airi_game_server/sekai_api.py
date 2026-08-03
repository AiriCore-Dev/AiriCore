import json
import time
import datetime

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from nonebot import get_driver, logger

from . import accounts, auth, ratelimit

_driver_config = get_driver().config

GRANT_CAP = 10000
GRANT_DAILY_CAP = int(
    getattr(_driver_config, "web_grant_daily_cap", 0) or 100000
)
SCORE_MAX = 10_000_000

POLL_PER_CODE = 400
POLL_PER_IP = 600

SEKAI_DAILY_LIMIT = 3

RUN_BLOB_MAX = 256 * 1024

BOARD_CACHE_TTL = 15.0
_board_cache: dict = {}

router = APIRouter()


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "") or "unknown"


def _need(key: str, limit: int, window: float) -> None:
    if not ratelimit.allow(key, limit, window):
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(ratelimit.retry_after(key, window))},
        )


def _auth_qq(authorization: str) -> str:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    qq = auth.verify_token(token)
    if not qq:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return qq


def _mask_qq(qq: str) -> str:
    if len(qq) <= 4:
        return qq[:1] + "*" * (len(qq) - 1)
    return qq[:2] + "*" * (len(qq) - 4) + qq[-2:]


def _today_str() -> str:
    n = datetime.datetime.now()
    return f"{n.year}-{n.month:02d}-{n.day:02d}"


def _require_today(value: str) -> str:
    date = value.strip()[:10]
    today = _today_str()
    if date != today:
        raise HTTPException(status_code=400, detail="日期必须为今天")
    return today


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
    id: str
    score: int


class RunBody(BaseModel):
    rev: int = 0
    run: dict | None = None


@router.post("/api/auth/request")
async def auth_request(request: Request):
    _need(f"authreq:{_client_ip(request)}", 10, 60)
    code = auth.new_code()
    return {"code": code, "ttl": auth.CODE_TTL}


@router.get("/api/auth/poll")
async def auth_poll(code: str, request: Request):
    _need(f"authpoll-code:{auth.normalize_code(code)}", POLL_PER_CODE, auth.CODE_TTL + 60)
    _need(f"authpoll-ip:{_client_ip(request)}", POLL_PER_IP, 60)
    res = auth.poll_code(code)
    if res is None:
        return {"bound": False}
    qq, nick = res
    accounts.ensure_account(qq)
    acc = accounts.get_account(qq)
    acc["web_nick"] = nick
    token = auth.issue_token(qq)
    return {"bound": True, "token": token, "qq": qq, "nick": nick,
            "credits": int(acc.get("credits", 0))}


@router.get("/api/me")
async def me(authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    acc = accounts.ensure_account(qq)
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
        "daily_started": used_today >= SEKAI_DAILY_LIMIT,
        "daily_used": used_today,
        "daily_limit": SEKAI_DAILY_LIMIT,
        "run_rev": int(run_rec.get("rev", 0)),
        "has_run": run_rec.get("run") is not None,
    }


@router.post("/api/credits/spend")
async def credits_spend(body: SpendBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    amount = int(body.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须为正")
    acc = accounts.ensure_account(qq)
    cur = int(acc.get("credits", 0))
    if cur < amount:
        return JSONResponse(status_code=402,
                            content={"ok": False, "credits": cur, "detail": "积分不足"})
    acc["credits"] = cur - amount
    return {"ok": True, "credits": acc["credits"]}


@router.post("/api/credits/grant")
async def credits_grant(body: GrantBody, request: Request,
                        authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    _need(f"grant:{qq}", 20, 60)
    amount = int(body.amount)
    if amount < 0:
        raise HTTPException(status_code=400, detail="金额不能为负")
    amount = min(amount, GRANT_CAP)
    acc = accounts.ensure_account(qq)
    today = _today_str()
    granted = acc.setdefault("web_granted", {})
    if not isinstance(granted, dict):
        granted = {}
        acc["web_granted"] = granted
    for stale in [d for d in granted if d != today]:
        granted.pop(stale, None)
    used = int(granted.get(today, 0))
    if used >= GRANT_DAILY_CAP:
        logger.warning(f"SEKAI 网页加分已达当日上限: qq={qq} used={used}")
        return JSONResponse(
            status_code=429,
            content={"ok": False, "credits": int(acc.get("credits", 0)),
                     "detail": "今日网页获取积分已达上限"},
        )
    amount = min(amount, GRANT_DAILY_CAP - used)
    granted[today] = used + amount
    acc["credits"] = int(acc.get("credits", 0)) + amount
    logger.info(
        f"SEKAI 网页加分: qq={qq} amount={amount} 今日累计={granted[today]} "
        f"reason={str(body.reason)[:40]} ip={_client_ip(request)}"
    )
    return {"ok": True, "credits": acc["credits"], "granted_today": granted[today]}


@router.post("/api/sekai/claim")
async def sekai_claim(body: ClaimBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    date = _require_today(body.date)
    acc = accounts.ensure_account(qq)
    started = acc.setdefault("sekai_started", {})
    for stale in [d for d in started if d != date]:
        started.pop(stale, None)
    used = int(started.get(date, 0))
    best = int(acc.get("sekai_daily", {}).get(date, 0))
    if used >= SEKAI_DAILY_LIMIT:
        return {"ok": False, "started": True, "used": used,
                "limit": SEKAI_DAILY_LIMIT, "best": best}
    started[date] = used + 1
    return {"ok": True, "started": True, "used": used + 1,
            "limit": SEKAI_DAILY_LIMIT, "best": best}


@router.post("/api/sekai/score")
async def sekai_score(body: ScoreBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    _need(f"score:{qq}", 30, 60)
    score = max(0, int(body.score))
    if score > SCORE_MAX:
        logger.warning(f"SEKAI 上报分数异常偏高，已截断: qq={qq} score={score}")
        score = SCORE_MAX
    date = _require_today(body.date)
    acc = accounts.ensure_account(qq)
    if int(acc.get("sekai_started", {}).get(date, 0)) <= 0:
        raise HTTPException(status_code=400, detail="请先开始今日对局")
    daily = acc.setdefault("sekai_daily", {})
    daily[date] = max(int(daily.get(date, 0)), score)
    return {"ok": True, "best": daily[date]}


def _cached_board(cache_key: str, builder):
    now = time.time()
    hit = _board_cache.get(cache_key)
    if hit and now - hit[0] <= BOARD_CACHE_TTL:
        return hit[1]
    rows = builder()
    if len(_board_cache) > 500:
        _board_cache.clear()
    _board_cache[cache_key] = (now, rows)
    return rows


@router.get("/api/sekai/board")
async def sekai_board(date: str, request: Request, limit: int = 20):
    _need(f"board:{_client_ip(request)}", 60, 60)
    date = date.strip()[:10]
    limit = max(1, min(100, int(limit)))

    def build():
        rows = []
        for qq, acc in accounts.get_data().items():
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
        return rows[:100]

    rows = _cached_board(f"daily:{date}", build)
    return {"date": date, "rows": rows[:limit]}


ACTIVITY_ID_MAX = 64
ACTIVITY_COUNT_MAX = 128


@router.post("/api/sekai/activity/score")
async def sekai_activity_score(body: ActScoreBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    _need(f"actscore:{qq}", 30, 60)
    aid = body.id.strip()[:ACTIVITY_ID_MAX]
    if not aid:
        raise HTTPException(status_code=400, detail="缺少活动 id")
    score = max(0, int(body.score))
    if score > SCORE_MAX:
        logger.warning(f"SEKAI 活动分数异常偏高，已截断: qq={qq} score={score}")
        score = SCORE_MAX
    acc = accounts.ensure_account(qq)
    act = acc.setdefault("sekai_activity", {})
    if aid not in act and len(act) >= ACTIVITY_COUNT_MAX:
        raise HTTPException(status_code=400, detail="活动记录数量已达上限")
    act[aid] = max(int(act.get(aid, 0)), score)
    return {"ok": True, "id": aid, "best": act[aid]}


@router.get("/api/sekai/activity/board")
async def sekai_activity_board(id: str, request: Request, limit: int = 20):
    _need(f"actboard:{_client_ip(request)}", 60, 60)
    aid = id.strip()[:ACTIVITY_ID_MAX]
    if not aid:
        raise HTTPException(status_code=400, detail="缺少活动 id")
    limit = max(1, min(100, int(limit)))

    def build():
        rows = []
        for qq, acc in accounts.get_data().items():
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
        return rows[:100]

    rows = _cached_board(f"act:{aid}", build)
    return {"id": aid, "rows": rows[:limit]}


@router.get("/api/sekai/load")
async def sekai_load(authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    acc = accounts.ensure_account(qq)
    rec = acc.get("sekai_run", {}) or {}
    return {"rev": int(rec.get("rev", 0)), "run": rec.get("run")}


@router.post("/api/sekai/save")
async def sekai_save(body: RunBody, authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    rev = int(body.rev)
    run = body.run

    if run is not None:
        try:
            size = len(json.dumps(run, ensure_ascii=False))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="对局数据无法序列化")
        if size > RUN_BLOB_MAX:
            raise HTTPException(status_code=413, detail="对局数据过大")

    acc = accounts.ensure_account(qq)
    rec = acc.get("sekai_run")
    if not isinstance(rec, dict):
        rec = {}
        acc["sekai_run"] = rec
    cur_rev = int(rec.get("rev", 0))
    if rev < cur_rev:
        return {"ok": False, "stale": True, "rev": cur_rev}
    rec["rev"] = rev
    rec["run"] = run
    return {"ok": True, "rev": rev}


@router.get("/api/health")
async def health():
    return {"ok": True}
