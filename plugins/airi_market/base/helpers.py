import os
import re
import hmac
import hashlib
import base64
from pathlib import Path

import yaml
import markdown as md_lib

from . import state
from . import cache as _cache


def image_url(article_name, filename):
    return f"https://{state.market_domain}:{state.market_port}/static/posts/{article_name}/{filename}"


def parse_article(article_name):
    article_dir = os.path.join(state.POSTS_DIR, article_name)
    index_path = Path(article_dir) / "index.md"

    cached = _cache.get_article(article_name, index_path)
    if cached is not None:
        return cached

    with open(index_path, "r", encoding="utf-8") as f:
        raw = f.read()

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except Exception:
            fm = {}
        body = raw[fm_match.end():]
    else:
        fm = {}
        body = raw

    title = fm.get("title", article_name)
    cover = fm.get("cover", "")

    def _replace_img(m):
        alt = m.group(1)
        src = m.group(2)
        if not src.startswith("http"):
            src = image_url(article_name, src)
        return f"![{alt}]({src})"

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace_img, body)

    html_content = md_lib.markdown(
        body,
        extensions=["extra", "nl2br"],
        output_format="html",
    )

    cover_url = image_url(article_name, cover) if cover else ""

    result = {
        "title": title,
        "cover_url": cover_url,
        "html_content": html_content,
    }
    _cache.put_article(article_name, index_path, result)
    return result


def list_articles():
    if not os.path.isdir(state.POSTS_DIR):
        return []
    return [
        d for d in os.listdir(state.POSTS_DIR)
        if os.path.isdir(os.path.join(state.POSTS_DIR, d))
        and os.path.isfile(os.path.join(state.POSTS_DIR, d, "index.md"))
    ]


def make_token(qq):
    secret = state.data.get("token_secret", "fallback").encode()
    mac = hmac.new(secret, str(qq).encode(), hashlib.sha256).digest()[:8]
    payload = mac + str(qq).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def verify_token(token):
    try:
        padded = token + "=" * (4 - len(token) % 4)
        payload = base64.urlsafe_b64decode(padded)
        mac = payload[:8]
        qq = payload[8:].decode()
        secret = state.data.get("token_secret", "fallback").encode()
        expected = hmac.new(secret, qq.encode(), hashlib.sha256).digest()[:8]
        if hmac.compare_digest(mac, expected):
            return qq
    except Exception:
        pass
    return None


def parse_market_args(arg_text):
    group_ids = None
    bot_ids = None
    tokens = re.split(r'\s+--', arg_text)
    article_name = tokens[0].strip()
    for token in tokens[1:]:
        m = re.match(r'^(group|bot)\s+([\d,]+)', token.strip())
        if m:
            flag, val = m.group(1), m.group(2)
            ids = {v for v in val.split(',') if v.isdigit()}
            if not ids:
                continue
            if flag == 'group':
                group_ids = (group_ids or set()) | ids
            else:
                bot_ids = (bot_ids or set()) | ids
    return article_name, group_ids, bot_ids


async def get_all_users(bots, group_ids=None, bot_ids=None):
    users = set()
    for bot in bots:
        if bot_ids is not None and str(bot.self_id) not in bot_ids:
            continue
        try:
            groups = await bot.get_group_list()
        except Exception:
            continue
        for group in groups:
            gid = str(group["group_id"])
            if group_ids is not None and gid not in group_ids:
                continue
            try:
                members = await bot.get_group_member_list(group_id=group["group_id"])
                for m in members:
                    uid = str(m["user_id"])
                    if uid != str(bot.self_id):
                        users.add(uid)
            except Exception:
                pass
    return users


def send_email(dest, subject, text, html_body=None):
    state.email_list.append([dest, subject, text, html_body])
