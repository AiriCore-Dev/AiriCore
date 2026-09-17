import re
from dataclasses import dataclass

from ..dialogue.parser import SPRITE_RE, _tokens


@dataclass(frozen=True, slots=True)
class DebateRequest:
    sprite: str
    side: str
    text: str


def split_highlights(text: str) -> tuple[tuple[str, bool], ...]:
    parts = text.split("**")
    if len(parts) % 2 == 0:
        raise ValueError("粉色文字的 ** 标记没有闭合")
    if any(not part.strip() for part in parts[1::2]):
        raise ValueError("** 内请填写需要强调的文字")
    return tuple((part, bool(index % 2)) for index, part in enumerate(parts) if part)


def validate_request(request: DebateRequest) -> DebateRequest:
    if not SPRITE_RE.fullmatch(request.sprite):
        raise ValueError("立绘短码格式无效")
    if request.side not in {"left", "right"}:
        raise ValueError("请使用 -左 或 -右 指定人物位置")
    if not request.text.strip() or len(request.text) > 2000:
        raise ValueError("审问正文须为 1～2000 字")
    if len(request.text.split("\n")) > 8:
        raise ValueError("审问正文最多支持八行，请减少换行")
    runs = split_highlights(request.text)
    if not "".join(text for text, _ in runs).strip():
        raise ValueError("审问正文不能为空")
    return request


def parse_debate(text: str) -> DebateRequest:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sprite = None
    side = None
    body = []
    pending = ""
    for token in _tokens(text):
        value = token.value
        if not token.protected and value.startswith("#"):
            if not SPRITE_RE.fullmatch(value):
                raise ValueError(f"立绘短码无效：{value}")
            if sprite is not None:
                raise ValueError("一张审问图只能指定一个立绘短码")
            sprite = value.upper()
        elif not token.protected and value in {"-左", "-右"}:
            if side is not None:
                raise ValueError("只能指定一次人物位置：-左 或 -右")
            side = "left" if value == "-左" else "right"
        else:
            separator = pending + token.separator
            if pending:
                separator = re.sub(r"[^\n]", "", separator) if "\n" in separator else " "
            if body:
                body.append(separator)
            body.append(value)
            pending = ""
            continue
        pending += token.separator
    if sprite is None:
        raise ValueError("请指定一个立绘短码，可通过魔裁立绘获取")
    if side is None:
        raise ValueError("请使用 -左 或 -右 指定人物位置")
    return validate_request(DebateRequest(sprite, side, "".join(body).replace("<br>", "\n")))
