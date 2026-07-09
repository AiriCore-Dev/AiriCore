import math
import json
import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import auth, store

GRANT_CAP = 10000

SEKAI_DAILY_LIMIT = 3

RUN_BLOB_MAX = 256 * 1024

app = FastAPI(title="SEKAI Roguelike API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
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
    store.ensure_account(qq)
    acc = store.get_account(qq)
    acc["web_nick"] = nick
    token = auth.issue_token(qq)
    return {"bound": True, "token": token, "qq": qq, "nick": nick,
            "credits": int(acc.get("credits", 0))}


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
        "daily_started": used_today >= SEKAI_DAILY_LIMIT,
        "daily_used": used_today,
        "daily_limit": SEKAI_DAILY_LIMIT,
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
    if cur < amount:
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
    amount = min(amount, GRANT_CAP)
    acc = store.ensure_account(qq)
    acc["credits"] = int(acc.get("credits", 0)) + amount
    return {"ok": True, "credits": acc["credits"]}


@app.post("/api/sekai/claim")
async def sekai_claim(body: ClaimBody, authorization: str = Header(default="")):
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


ACTIVITY_ID_MAX = 64


@app.post("/api/sekai/activity/score")
async def sekai_activity_score(body: ActScoreBody, authorization: str = Header(default="")):
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


@app.get("/api/sekai/load")
async def sekai_load(authorization: str = Header(default="")):
    qq = _auth_qq(authorization)
    acc = store.ensure_account(qq)
    rec = acc.get("sekai_run", {}) or {}
    return {"rev": int(rec.get("rev", 0)), "run": rec.get("run")}


@app.post("/api/sekai/save")
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

    acc = store.ensure_account(qq)
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


@app.get("/api/health")
async def health():
    return {"ok": True}
