import os
import re
import sys
import json
import time
import shutil

TEMPLATE_NAME = ".env.prod_example"
TARGET_NAME = ".env.prod"
KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(\s*)=(\s*)(.*)$")
COMMENT_COL = 39


class QuitWizard(Exception):
    pass


def split_comment(rest):
    in_q = False
    for i, ch in enumerate(rest):
        if ch == '"':
            in_q = not in_q
        elif ch == "#" and not in_q:
            return rest[:i], rest[i:]
    return rest, ""


def parse_records(text):
    records = []
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        m = KV_RE.match(line)
        if not m:
            records.append({"kind": "raw", "text": line})
            continue
        value, comment = split_comment(m.group(4))
        comment = comment.strip()
        records.append({
            "kind": "kv",
            "key": m.group(1),
            "value": value.strip(),
            "comment": comment,
            "col": line.rfind(comment) if comment else COMMENT_COL,
        })
    return records


def render_records(records):
    lines = []
    for r in records:
        if r["kind"] == "raw":
            lines.append(r["text"])
            continue
        head = r["key"] + " = " + r["value"]
        if r["comment"]:
            pad = max(1, r.get("col", COMMENT_COL) - len(head))
            lines.append(head + " " * pad + r["comment"])
        else:
            lines.append(head)
    return "\r\n".join(lines)


def clean_scalar(s):
    return s.replace("#", "").replace('"', "").replace("\r", "").replace("\n", "").strip()


def decode_list(value):
    v = (value or "").strip()
    if not v:
        return []
    try:
        data = json.loads(v)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    v = v.strip("[]")
    return [clean_scalar(x) for x in v.split(",") if clean_scalar(x)]


def encode_list(items):
    return "[" + ",".join('"' + clean_scalar(x) + '"' for x in items) + "]"


def decode_bool(value):
    return clean_scalar(value).lower() in ("1", "true", "yes", "y", "on")


def encode_bool(flag):
    return "true" if flag else "false"


def decode_text(value):
    v = (value or "").strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


def encode_text(value, quoted=True):
    v = clean_scalar(value)
    return '"' + v + '"' if quoted else v


def out(text=""):
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, "replace").decode(enc, "replace"))


def rule(char="-", width=64):
    out(char * width)


def banner():
    rule("=")
    out("        AiriCore 配置向导")
    rule("=")
    out("这个向导会一步步问你几个问题, 帮你生成 .env.prod 配置文件。")
    out("完全不懂技术也没关系, 按提示做就行:")
    out("  - 看到 [直接回车] 说明可以什么都不填, 用括号里的默认值")
    out("  - 输入 ? 再回车, 会告诉你这一项到底是什么、去哪里找")
    out("  - 输入 q 再回车, 随时退出向导 (不会改动任何文件)")
    out("  - 中途填错不要紧, 之后可以重新跑这个向导, 或手动改 .env.prod")
    rule()
    out()


def ask_raw(prompt):
    try:
        val = input(prompt)
    except EOFError:
        raise QuitWizard()
    except KeyboardInterrupt:
        out()
        raise QuitWizard()
    if val.strip().lower() == "q":
        raise QuitWizard()
    return val.strip()


def ask_yes_no(question, default_yes=True):
    tail = "[Y/n]" if default_yes else "[y/N]"
    while True:
        val = ask_raw(question + " " + tail + " ").lower()
        if not val:
            return default_yes
        if val in ("y", "yes", "是", "要", "1"):
            return True
        if val in ("n", "no", "否", "不", "0"):
            return False
        out("  请输入 y (是) 或 n (否), 也可以直接回车用默认值。")


def mask(value):
    if not value:
        return "(空)"
    if len(value) <= 6:
        return value[0] + "***"
    return value[:3] + "***" + value[-3:]


def v_qq(value):
    if not re.fullmatch(r"\d{5,12}", value):
        return "QQ 号应该是 5-12 位纯数字, 例如 864623174"
    return None


def v_url(value):
    if not value.startswith("http://") and not value.startswith("https://"):
        return "要以 http:// 或 https:// 开头, 例如 https://api.openai.com/v1"
    return None


def v_port(value):
    if not value.isdigit() or not (1 <= int(value) <= 65535):
        return "端口要是 1-65535 之间的数字"
    return None


def v_hour(value):
    if not value.isdigit() or not (0 <= int(value) <= 23):
        return "小时要是 0-23 之间的数字 (24 小时制)"
    return None


def v_int(value):
    if not value.isdigit():
        return "要是纯数字"
    return None


def v_email(value):
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        return "邮箱格式不对, 例如 airi@example.com"
    return None


def v_plugin(value):
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        return "插件名只能是英文、数字、下划线, 例如 airi_switch"
    return None


def show_help(item):
    out("  " + "-" * 60)
    for line in item.get("help", ["暂无更多说明, 不确定就直接回车用默认值。"]):
        out("  | " + line)
    if item.get("example"):
        out("  | 填写示例: " + item["example"])
    out("  " + "-" * 60)


def default_hint(item, current):
    t = item["type"]
    if t == "list":
        items = decode_list(current)
        return ", ".join(items) if items else "留空"
    if t == "bool":
        return "是" if decode_bool(current) else "否"
    if t == "secret":
        return mask(decode_text(current)) if decode_text(current) else "留空"
    val = decode_text(current)
    return val if val else "留空"


def ask_item(item, current, step, total):
    t = item["type"]
    out("[%d/%d] %s" % (step, total, item["q"]))
    for line in item.get("tip", []):
        out("      " + line)
    hint = default_hint(item, current)
    while True:
        if t == "bool":
            cur = decode_bool(current)
            tail = "[Y/n]" if cur else "[y/N]"
            val = ask_raw("      直接回车 = " + hint + " | ? = 说明 " + tail + ": ").lower()
            if val == "?":
                show_help(item)
                continue
            if not val:
                out()
                return encode_bool(cur)
            if val in ("y", "yes", "是", "要", "1"):
                out()
                return encode_bool(True)
            if val in ("n", "no", "否", "不", "0"):
                out()
                return encode_bool(False)
            out("      请输入 y (是) 或 n (否)。")
            continue
        prompt = "      直接回车 = " + hint + " | ? = 说明\n      请输入: "
        val = ask_raw(prompt)
        if val == "?":
            show_help(item)
            continue
        if not val:
            has_now = bool(decode_list(current)) if t == "list" else bool(decode_text(current))
            if item.get("required") and not has_now:
                out("      提示: 这一项留空的话, 相关功能用不了 (Bot 还是能启动)。")
                if not ask_yes_no("      再按一次回车就跳过, 或输入 n 回去重填。跳过?", default_yes=True):
                    continue
            out()
            return current
        if t == "list":
            parts = [p for p in re.split(r"[,，\s]+", val) if p]
            bad = None
            fn = item.get("validate")
            if fn:
                for p in parts:
                    bad = fn(clean_scalar(p))
                    if bad:
                        break
            if bad:
                out("      " + bad)
                continue
            out()
            return encode_list(parts)
        if t == "choice":
            pick = clean_scalar(val).lower()
            if pick not in item["choices"]:
                out("      只能填: " + " / ".join(item["choices"]))
                continue
            out()
            return encode_text(pick, item.get("quoted", True))
        cleaned = clean_scalar(val)
        fn = item.get("validate")
        if fn:
            bad = fn(cleaned)
            if bad:
                out("      " + bad)
                continue
        out()
        return encode_text(cleaned, item.get("quoted", True))


STEP_BASE = {
    "title": "第一部分: 基础连接 (必填)",
    "why": [
        "这几项决定谁能管 Bot、Bot 叫什么、以及 QQ 客户端(NapCat/Lagrange 等)怎么连上来。",
        "不填也能启动, 但你将无法用管理员指令控制 Bot。",
    ],
    "items": [
        {
            "key": "SUPERUSERS",
            "type": "list",
            "q": "谁是 Bot 的管理员? 请填 QQ 号",
            "tip": ["多个 QQ 号用空格或逗号隔开"],
            "validate": v_qq,
            "required": True,
            "example": "864623174 3630532026",
            "help": [
                "管理员 = 能对 Bot 发管理指令的人 (重启、封禁、开关插件等)。",
                "填你自己的 QQ 号就行, 就是你登录 QQ 用的那串数字。",
                "不知道自己 QQ 号: 手机 QQ 里点头像 -> 资料页可以看到。",
                "填错了 Bot 也能跑, 只是你没有管理权限。",
            ],
        },
        {
            "key": "nickname",
            "type": "list",
            "q": "你希望大家怎么叫这个 Bot?",
            "tip": ["群里喊这个名字 Bot 就会理你, 可以填多个"],
            "example": "Airi 爱莉",
            "help": [
                "这是 Bot 的昵称。群友在群里说 '爱莉 你好', Bot 就知道是在叫它。",
                "可以填多个, 用空格隔开, 都会生效。",
                "留空的话就只能靠 @ Bot 来触发了。",
            ],
        },
        {
            "key": "ONEBOT_ACCESS_TOKEN",
            "type": "secret",
            "q": "QQ 客户端连接用的密码 (Access Token)",
            "tip": ["必须和 NapCat / Lagrange 里填的那串一模一样"],
            "example": "airi-secret-2026",
            "help": [
                "这不是你的 QQ 密码! 它是 Bot 和 QQ 客户端之间的对讲暗号。",
                "你在 NapCat (或 Lagrange 等) 的反向 WS 设置里填了什么, 这里就填一样的。",
                "两边不一致的话, QQ 客户端会一直连不上 Bot。",
                "还没设置的话: 自己想一串英文数字, 两边填同一个即可。",
                "本机自己玩、不担心被人乱连, 也可以直接回车留空。",
            ],
        },
        {
            "key": "PORT",
            "type": "text",
            "quoted": False,
            "q": "Bot 监听的端口号",
            "tip": ["不懂就直接回车, 用 15100"],
            "validate": v_port,
            "help": [
                "端口 = QQ 客户端来敲门的门牌号。NapCat 里要填 ws://你的地址:这个端口/onebot/v11/ws",
                "默认 15100 一般不用改。只有当这个端口被别的程序占了才需要换。",
            ],
        },
        {
            "key": "enable_ssl",
            "type": "bool",
            "q": "要启用 SSL 加密吗?",
            "tip": ["默认关闭, QQ 客户端地址使用 ws://; 有证书时才选是"],
            "help": [
                "关闭时 bot.py 与 airi_market 会跳过 SSL 启动参数, 使用普通 HTTP/WS。",
                "启用时需要准备 ./utils/ssl/privkey.key 与 ./utils/ssl/fullchain.pem。",
                "默认关闭适合本机或由反向代理负责 HTTPS 的部署。",
            ],
        },
    ],
}

STEP_LLM = {
    "title": "第二部分: AI 大模型 (聊天功能的核心)",
    "why": [
        "Bot 的聊天、翻译、内容审核都靠这里的大模型。",
        "你需要一个兼容 OpenAI 接口的服务地址和密钥 (官方 OpenAI、国内中转站、自建都行)。",
        "不填的话 Bot 能启动, 但不会聊天。",
    ],
    "items": [
        {
            "key": "airi_char_name",
            "type": "text",
            "q": "Bot 的人设名字叫什么?",
            "tip": ["会写进 AI 的人设提示词里"],
            "example": "Airi",
            "help": [
                "告诉 AI '你叫什么', 影响它自我介绍时的说法。",
                "一般填和昵称一样的名字。",
            ],
        },
        {
            "key": "airi_char_aliases",
            "type": "list",
            "q": "还有哪些叫法算是在叫它?",
            "tip": ["多个用空格隔开, 会用来判断有没有人在喊 Bot"],
            "example": "airi 爱莉",
            "help": [
                "群友说到这些词, Bot 就认为在叫自己, 可能会接话。",
                "注意别填太常见的字, 否则 Bot 会一直插话。",
            ],
        },
    ],
}

STEP_MC = {
    "title": "第三部分: Minecraft 服务器管理 (可选)",
    "optional": True,
    "ask": "你要用 Bot 管理 Minecraft 服务器吗? (没有 MC 服就选 n)",
    "why": [
        "开启后可以在群里查在线玩家、加白名单、执行服务器指令。",
        "需要你的 MC 服务端已经开了 RCON (server.properties 里 enable-rcon=true)。",
    ],
    "items": [
        {
            "key": "rcon_host",
            "type": "text",
            "q": "MC 服务器地址",
            "tip": ["和 Bot 装在同一台机器就直接回车"],
            "example": "127.0.0.1",
            "help": [
                "127.0.0.1 表示 '就是本机'。MC 服和 Bot 在同一台机器上就用这个。",
                "如果 MC 服在另一台机器, 填那台机器的 IP。",
            ],
        },
        {
            "key": "rcon_port",
            "type": "text",
            "quoted": False,
            "q": "RCON 端口",
            "tip": ["看 server.properties 里的 rcon.port, 默认 25575"],
            "validate": v_port,
            "help": [
                "打开 MC 服务端目录里的 server.properties 文件, 找 rcon.port 那一行。",
                "默认就是 25575, 多数人不会改。",
            ],
        },
        {
            "key": "rcon_password",
            "type": "secret",
            "q": "RCON 密码",
            "tip": ["就是 server.properties 里 rcon.password 的值"],
            "help": [
                "打开 server.properties, 找 rcon.password 那一行, 等号后面就是密码。",
                "同时确认 enable-rcon=true, 否则连不上。",
                "改完 server.properties 需要重启 MC 服才生效。",
            ],
        },
        {
            "key": "mc_whitelist_groups",
            "type": "list",
            "q": "哪些群可以发服管指令?",
            "tip": ["填群号, 多个用空格隔开"],
            "validate": v_int,
            "example": "740774974 466470972",
            "help": [
                "只有列在这里的群, 才能用 / 开头的服务器管理指令。",
                "群号在群设置里能看到, 是一串数字。",
                "留空会用代码里的内置默认群号, 建议自己填。",
            ],
        },
        {
            "key": "mc_server_path",
            "type": "text",
            "q": "MC 服务端目录的完整路径",
            "tip": ["不知道就直接回车跳过"],
            "example": "/root/airi/airicob5",
            "help": [
                "用于读取服务器文件 (如日志、白名单)。",
                "Windows 写法像 D:\\mcserver, Linux/macOS 写法像 /home/mc/server。",
                "留空只影响少数依赖读文件的功能, 普通指令照样能用。",
            ],
        },
    ],
}

STEP_MAIL = {
    "title": "第四部分: 邮件发送 (可选)",
    "optional": True,
    "ask": "你要启用邮件发送吗? (许愿瓶审核和营销推送需要它)",
    "why": [
        "开启后 Bot 能用你的邮箱发信。",
        "你需要一个支持 SMTP 的邮箱, 并拿到它的 '授权码' (不是登录密码)。",
        "QQ 邮箱: 设置 -> 账号 -> 开启 SMTP 服务 -> 生成授权码。",
    ],
    "items": [
        {
            "key": "email_smtp_host",
            "type": "text",
            "q": "SMTP 服务器地址",
            "tip": ["QQ 邮箱填 smtp.qq.com"],
            "example": "smtp.qq.com",
            "help": [
                "常见的几个: QQ 邮箱 smtp.qq.com, 163 邮箱 smtp.163.com, Gmail smtp.gmail.com。",
                "企业邮箱去自己后台查 'SMTP 发信服务器'。",
            ],
        },
        {
            "key": "email_smtp_user",
            "type": "text",
            "q": "SMTP 登录账号",
            "tip": ["一般就是你的完整邮箱地址"],
            "validate": v_email,
            "example": "airi@qq.com",
            "help": [
                "多数服务商就是填完整邮箱地址。",
                "少数企业邮箱只要 @ 前面那段, 按你后台的说明填。",
            ],
        },
        {
            "key": "email_smtp_password",
            "type": "secret",
            "q": "SMTP 授权码",
            "tip": ["注意: 是授权码, 不是邮箱登录密码"],
            "help": [
                "QQ 邮箱: 网页版 -> 设置 -> 账号 -> POP3/SMTP 服务开启后, 会给你一串 16 位授权码。",
                "163 邮箱同理, 在 '客户端授权密码' 里生成。",
                "直接填登录密码通常会报认证失败。",
            ],
        },
        {
            "key": "email_from_address",
            "type": "text",
            "q": "发件人邮箱地址",
            "tip": ["收信人看到的 '来自' 就是这个"],
            "validate": v_email,
            "example": "airi@qq.com",
            "help": [
                "通常和上面的登录账号填一样。",
                "填成和登录账号不同的地址, 很多服务商会拒收。",
            ],
        },
        {
            "key": "email_from_name",
            "type": "text",
            "q": "发件人显示名称",
            "tip": ["直接回车用 AiriCore Service"],
            "example": "AiriCore Service",
            "help": ["收信人在收件箱里看到的名字, 随便起, 不影响功能。"],
        },
    ],
}

STEP_MARKET = {
    "title": "第五部分: 营销邮件推送 (可选, 进阶)",
    "optional": True,
    "ask": "你要用群发邮件推广功能吗? (需要一个能公网访问的域名, 新手建议选 n)",
    "why": [
        "它会给群成员群发文章邮件, 并提供一个网页让人退订。",
        "退订链接要能被外网打开, 所以必须有域名并且端口对外开放。",
        "只是自己玩的话完全不需要, 选 n 跳过。",
    ],
    "items": [
        {
            "key": "market_domain",
            "type": "text",
            "q": "你的公网域名",
            "tip": ["退订链接会用这个域名拼出来"],
            "example": "airi.example.com",
            "help": [
                "只填域名本身, 不要带 https:// 也不要带斜杠。",
                "这个域名要解析到跑 Bot 的这台机器, 并且下面那个端口能从外网访问。",
                "没有域名就回到上一步选 n 跳过整个功能。",
            ],
        },
        {
            "key": "market_port",
            "type": "text",
            "quoted": False,
            "q": "退订网页服务的端口",
            "tip": ["直接回车用 22320"],
            "validate": v_port,
            "help": [
                "要在防火墙/安全组里放行这个端口, 否则别人打不开退订页。",
                "云服务器还要去控制台的安全组里加规则。",
            ],
        },
        {
            "key": "market_daily_limit",
            "type": "text",
            "quoted": False,
            "q": "每天最多发多少封邮件?",
            "tip": ["直接回车用 3000"],
            "validate": v_int,
            "help": [
                "发太多容易被邮箱服务商判定为垃圾邮件并封号。",
                "刚开始建议压低一点, 比如 200-500。",
            ],
        },
        {
            "key": "market_send_start_hour",
            "type": "text",
            "quoted": False,
            "q": "每天几点开始发? (0-23)",
            "tip": ["直接回车用 8 点"],
            "validate": v_hour,
            "help": ["24 小时制。8 表示早上 8 点。太早发信容易打扰人。"],
        },
        {
            "key": "market_send_end_hour",
            "type": "text",
            "quoted": False,
            "q": "每天几点停止发? (0-23)",
            "tip": ["直接回车用 21 点"],
            "validate": v_hour,
            "help": ["24 小时制。21 表示晚上 9 点。要比开始时间大。"],
        },
    ],
}

STEP_OPS = {
    "title": "第六部分: 运行与省内存设置",
    "why": [
        "这部分决定 Bot 吃多少内存、出问题时通知谁、以及晚上要不要闭嘴。",
        "全部直接回车也没问题, 默认值适合大多数机器。",
    ],
    "items": [
        {
            "key": "cache_mode",
            "type": "choice",
            "quoted": False,
            "choices": ["ram", "balanced", "disk"],
            "q": "缓存模式选哪个? (ram / balanced / disk)",
            "tip": ["内存小于 4G 建议填 disk, 不确定就直接回车用 balanced"],
            "example": "balanced",
            "help": [
                "ram      = 全部塞进内存, 最快, 但启动时会吃掉好几个 G 内存。",
                "balanced = 内存加磁盘混着用, 速度和内存都还行 (推荐)。",
                "disk     = 尽量用磁盘, 最省内存, 出图会慢一点。",
                "小内存的云服务器 (1G/2G) 请一定选 disk, 否则可能被系统杀掉进程。",
            ],
        },
        {
            "key": "notification_account",
            "type": "text",
            "q": "系统通知发给哪个 QQ?",
            "tip": ["Bot 出错、重启会私聊这个号, 一般填你自己"],
            "validate": v_qq,
            "example": "864623174",
            "help": [
                "填一个 QQ 号, Bot 会把运行状态、异常提醒私聊发给它。",
                "留空则不发通知。",
                "注意: Bot 要和这个号是好友, 否则可能发不出去。",
            ],
        },
        {
            "key": "notification_bot_account",
            "type": "text",
            "q": "系统通知由哪个 Bot 账号发送?",
            "tip": ["填在线 Bot 的 QQ 号, 留空则自动选择第一个在线 Bot"],
            "validate": v_qq,
            "example": "1330248395",
            "help": [
                "这个账号决定 airi_notice 和 airi_wish_bottle 使用哪个 Bot 发私聊通知。",
                "留空时会从当前在线 Bot 中自动选择, 建议生产环境固定填写。",
            ],
        },
        {
            "key": "curfew_bot_ids",
            "type": "list",
            "q": "哪些 Bot 需要晚上 23:00-6:00 静默?",
            "tip": ["填 Bot 自己的 QQ 号, 不需要就直接回车留空"],
            "validate": v_qq,
            "example": "1330248395",
            "help": [
                "宵禁 = 深夜时段 Bot 不说话, 避免半夜刷屏扰民。",
                "这里填的是 Bot 账号的 QQ 号, 不是你的。",
                "留空表示不启用宵禁, Bot 24 小时都会响应。",
            ],
        },
        {
            "key": "airifullgroup_bot_whitelist",
            "type": "list",
            "q": "哪些 Bot 可以执行全群广播?",
            "tip": ["只填允许广播的 Bot QQ 号, 多个用空格隔开, 留空表示禁止广播"],
            "validate": v_qq,
            "example": "1330248395 535071478",
            "help": [
                "airifullgroup 只会使用这里列出的 Bot 向所有群发送消息。",
                "这里填 Bot 自己的 QQ 号, 不是管理员 QQ 号。",
                "留空时不会有任何 Bot 执行全群广播, 用于防止误发。",
            ],
        },
        {
            "key": "_2fa_key",
            "type": "secret",
            "q": "二步验证密钥 (SUPERUSER 管理功能必需)",
            "tip": ["用于所有 SUPERUSER 管理指令, 需要配合验证器 App"],
            "help": [
                "这是 TOTP 密钥 (Base32 格式), 配合 Google Authenticator 这类 App 用。",
                "配置后执行 SUPERUSER 管理指令要额外输入 6 位动态码。",
                "用法示例：airiflush 123456；也支持 123456 reboot。",
                "留空时 SUPERUSER 管理指令将被拒绝。",
            ],
        },
    ],
}

STEPS = [STEP_BASE, STEP_LLM, STEP_MC, STEP_MAIL, STEP_MARKET, STEP_OPS]

SUMMARY_GROUPS = [
    ("基础连接", [
        ("SUPERUSERS", False),
        ("nickname", False),
        ("PORT", False),
        ("enable_ssl", False),
        ("ONEBOT_ACCESS_TOKEN", True),
    ]),
    ("AI 大模型", []),
    ("Minecraft", [
        ("rcon_host", False),
        ("rcon_port", False),
        ("rcon_password", True),
    ]),
    ("邮件", [
        ("email_smtp_host", False),
        ("email_from_address", False),
        ("email_smtp_password", True),
    ]),
    ("营销推送", [
        ("market_domain", False),
    ]),
    ("运行设置", [
        ("cache_mode", False),
        ("notification_account", False),
        ("notification_bot_account", False),
        ("curfew_bot_ids", False),
        ("airifullgroup_bot_whitelist", False),
    ]),
]

SUMMARY_KEYS = [kv for _, group in SUMMARY_GROUPS for kv in group]

OPTIONAL_GROUPS = {"Minecraft": "MC", "邮件": "MAIL", "营销推送": "MARKET"}
STEP_TAGS = {"MC": STEP_MC, "MAIL": STEP_MAIL, "MARKET": STEP_MARKET}

REQUIRED_KEYS = ["SUPERUSERS"]

PROFILE_ITEMS = [
    {"key": "base_url", "type": "text", "q": "LLM Base URL", "tip": ["兼容 OpenAI 接口的服务地址"], "required": True, "validate": v_url},
    {"key": "token", "type": "secret", "q": "LLM API Key", "tip": ["密钥仅写入 data/LLM/default.conf"], "required": True},
    {"key": "chat_model", "type": "text", "q": "聊天主模型", "tip": ["支持图片的聊天模型"], "required": True},
    {"key": "chat_text_model", "type": "text", "q": "纯文本聊天模型", "tip": ["留空使用聊天主模型"]},
    {"key": "chat_fallback", "type": "list", "q": "聊天备用模型列表", "tip": ["逗号分隔，可留空"]},
    {"key": "other_model", "type": "text", "q": "辅助模型", "tip": ["翻译、审核等功能使用，可留空"]},
    {"key": "other_fallback", "type": "list", "q": "辅助备用模型列表", "tip": ["逗号分隔，可留空"]},
]


def load_profile_values(root):
    path = os.path.join(root, "data", "LLM", "default.conf")
    values = {}
    if not os.path.isfile(path):
        return values
    for line in read_text(path).splitlines():
        if "=" not in line or line.lstrip().startswith(("#", ";")):
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip().strip("'\"")
    return values


def write_profile(root, values):
    directory = os.path.join(root, "data", "LLM")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "default.conf")
    lines = []
    for key in ("base_url", "token", "chat_model", "chat_text_model", "chat_fallback", "other_model", "other_fallback"):
        value = values.get(key, "")
        if isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"{key} = {value}")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    out("    已写入 " + path)

def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_existing(path):
    if not os.path.isfile(path):
        return {}
    values = {}
    for r in parse_records(read_text(path)):
        if r["kind"] == "kv":
            values[r["key"]] = r["value"]
    return values


def count_items(steps):
    return sum(len(s["items"]) for s in steps)


def ensure_environment_file(root):
    path = os.path.join(root, ".env")
    try:
        if os.path.isfile(path):
            body = read_text(path)
            if "ENVIRONMENT" in body:
                return
            with open(path, "a", encoding="utf-8") as f:
                f.write("\nENVIRONMENT=prod\n")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write("ENVIRONMENT=prod\n")
        out("    已确认 .env 指向 prod 环境")
    except OSError as e:
        out("    警告: 写入 .env 失败: " + str(e))


def print_summary(values, skipped=None):
    skipped = skipped or set()
    out()
    rule("=")
    out("        配置结果确认 (密钥已打码)")
    rule("=")
    for group_name, group in SUMMARY_GROUPS:
        tag = OPTIONAL_GROUPS.get(group_name)
        if tag and tag in skipped:
            out("  [" + group_name + "]  (已跳过, 未启用)")
            out()
            continue
        out("  [" + group_name + "]")
        for key, secret in group:
            if key not in values:
                continue
            show_row(key, secret, values[key])
        out()
    missing = []
    for k in REQUIRED_KEYS:
        raw = values.get(k, "")
        filled = bool(decode_list(raw)) if raw.strip().startswith("[") else bool(decode_text(raw))
        if not filled:
            missing.append(k)
    if missing:
        out("注意: 以下必填项还是空的, 相关功能会不可用 (Bot 仍能启动):")
        for k in missing:
            out("  - " + k)
        out("你可以现在保存, 之后再重新跑这个向导补上。")
        rule()
    return missing


def show_row(key, secret, raw):
    if raw.strip().startswith("["):
        items = decode_list(raw)
        shown = ", ".join(items) if items else "(未填)"
    elif secret:
        plain = decode_text(raw)
        shown = mask(plain) if plain else "(未填)"
    else:
        shown = decode_text(raw) or "(未填)"
    out("  %-24s %s" % (key, shown))


def write_target(root, records, values):
    for r in records:
        if r["kind"] == "kv" and r["key"] in values:
            r["value"] = values[r["key"]]
    target = os.path.join(root, TARGET_NAME)
    if os.path.isfile(target):
        backup = target + ".bak." + time.strftime("%Y%m%d-%H%M%S")
        shutil.copyfile(target, backup)
        out("    原文件已备份为 " + os.path.basename(backup))
    body = render_records(records)
    if not body.endswith("\r\n"):
        body += "\r\n"
    with open(target, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    out("    已写入 " + target)


def fallback_copy(root, reason):
    target = os.path.join(root, TARGET_NAME)
    template = os.path.join(root, TEMPLATE_NAME)
    out("==> 跳过交互式配置: " + reason)
    if os.path.isfile(target):
        out("    .env.prod 已存在, 保持不变")
    else:
        shutil.copyfile(template, target)
        out("    已从示例创建 .env.prod, 启动前请手动编辑")
    out("    需要向导时可随时运行: python 一键部署脚本/_setup_env.py")
    return 0


def run_wizard(root, values, records):
    banner()
    total = count_items(STEPS)
    step_no = 0
    skipped = set()
    for step in STEPS:
        rule("=")
        out(step["title"])
        rule("=")
        for line in step["why"]:
            out("  " + line)
        out()
        if step.get("optional"):
            if not ask_yes_no("  " + step["ask"], default_yes=False):
                out("  已跳过这一部分, 相关配置保持原样。")
                out()
                for tag, ref in STEP_TAGS.items():
                    if ref is step:
                        skipped.add(tag)
                step_no += len(step["items"])
                continue
            out()
        for item in step["items"]:
            step_no += 1
            current = values.get(item["key"], "")
            values[item["key"]] = ask_item(item, current, step_no, total)
    profile_values = load_profile_values(root)
    out("第二部分补充: LLM 配置档 (写入 data/LLM/default.conf)")
    for item in PROFILE_ITEMS:
        step_no += 1
        profile_values[item["key"]] = ask_item(item, profile_values.get(item["key"], ""), step_no, total + len(PROFILE_ITEMS))
    print_summary(values, skipped)
    if not ask_yes_no("确认保存到 .env.prod 吗?", default_yes=True):
        out("已取消, 没有改动任何文件。")
        return 1
    write_target(root, records, values)
    write_profile(root, profile_values)
    ensure_environment_file(root)
    out()
    rule("=")
    out("配置完成! 接下来:")
    port = decode_text(values.get("PORT", "")) or "15100"
    out("  1. 打开 NapCat (或你用的 QQ 客户端), 添加反向 WebSocket:")
    scheme = "wss" if decode_bool(values.get("enable_ssl", "false")) else "ws"
    out("     " + scheme + "://127.0.0.1:" + port + "/onebot/v11/ws")
    if scheme == "wss":
        out("     用的是自签名证书, 客户端要勾选 '忽略证书校验' 之类的选项")
    out("     Token 填你刚才设置的那串 (留空就不用填)")
    out("  2. 运行启动脚本把 Bot 拉起来")
    out("  3. 想改配置: 重跑本向导, 或直接用记事本编辑 .env.prod")
    rule("=")
    return 0


def main():
    args = sys.argv[1:]
    root = None
    interactive = True
    force = False
    for a in args:
        if a == "--no-interactive":
            interactive = False
        elif a == "--force":
            force = True
        elif not a.startswith("--"):
            root = a
    if root is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template = os.path.join(root, TEMPLATE_NAME)
    target = os.path.join(root, TARGET_NAME)
    if not os.path.isfile(template):
        out("错误: 找不到模板文件 " + template)
        return 1
    if not interactive:
        return fallback_copy(root, "调用方指定了非交互模式")
    if not sys.stdin or not sys.stdin.isatty():
        return fallback_copy(root, "当前不是交互式终端")
    records = parse_records(read_text(template))
    values = {}
    for r in records:
        if r["kind"] == "kv":
            values[r["key"]] = r["value"]
    if os.path.isfile(target):
        values.update(load_existing(target))
        out()
        out("检测到已有的 .env.prod 配置文件。")
        out("向导会把现有的值作为默认值, 你只需要改想改的, 其它一路回车即可。")
        try:
            if not force and not ask_yes_no("要现在进入配置向导吗?", default_yes=False):
                out("保持现有 .env.prod 不变。")
                return 0
        except QuitWizard:
            out("已退出向导, 未改动任何文件。")
            return 0
    try:
        return run_wizard(root, values, records)
    except QuitWizard:
        out()
        out("已退出向导, 未改动任何文件。")
        if not os.path.isfile(target):
            shutil.copyfile(template, target)
            out("为了能启动, 已先从示例复制一份 .env.prod, 请稍后手动编辑。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
