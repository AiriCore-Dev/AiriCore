import re
from dataclasses import dataclass

from ..sprite_editor.state import CODE_ALPHABET, CODE_LENGTH
from ..utils import CHARACTER_NAME_MAP


SPRITE_RE = re.compile(rf"#[{CODE_ALPHABET}]{{{CODE_LENGTH}}}", re.IGNORECASE)
BACKGROUND_RE = re.compile(r"@BG[0-9]{3}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DialogueRequest:
    background: str
    sprites: tuple[str, ...]
    author: str | None
    text: str


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    separator: str
    protected: bool


def _tokens(text: str) -> list[_Token]:
    tokens = []
    separator = ""
    value = []
    protected = False
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is None and char.isspace():
            if value:
                tokens.append(_Token("".join(value), separator, protected))
                separator = ""
                value = []
                protected = False
            separator += char
        elif char == "\\":
            index += 1
            if index >= len(text):
                raise ValueError("反斜线后缺少要转义的字符")
            value.append("\n" if text[index] == "n" else text[index])
            protected = True
        elif quote is None and char in {'"', "'"}:
            quote = char
            protected = True
        elif quote == char:
            quote = None
        else:
            value.append(char)
        index += 1
    if quote is not None:
        raise ValueError("正文引号没有闭合")
    if value:
        tokens.append(_Token("".join(value), separator, protected))
    return tokens


def _body_separator(separator: str, has_body: bool) -> str:
    if not has_body:
        return ""
    if "\n" in separator or "\r" in separator:
        return re.sub(r"[ \t]*(\r?\n)[ \t]*", r"\1", separator)
    return " " if separator else ""


def parse_dialogue(text: str) -> DialogueRequest:
    background = None
    sprites = []
    author = None
    author_seen = False
    body = []
    pending_separator = ""
    for token in _tokens(text):
        value = token.value
        if not token.protected and value.startswith("#"):
            if not SPRITE_RE.fullmatch(value):
                raise ValueError(f"立绘短码无效：{value}")
            sprites.append(value.upper())
            if len(sprites) > 3:
                raise ValueError("一张对话图最多使用三个立绘")
        elif not token.protected and value.startswith("@"):
            if not BACKGROUND_RE.fullmatch(value):
                raise ValueError(f"背景短码无效：{value}")
            if background is not None:
                raise ValueError("只能指定一个背景")
            background = value.upper()
        elif not token.protected and value.startswith("*"):
            if author_seen:
                raise ValueError("只能指定一个姓名牌")
            author_seen = True
            name = value[1:]
            if name.lower() == "none":
                author = None
            elif name == "?":
                author = "?"
            else:
                try:
                    author = CHARACTER_NAME_MAP[name].value
                except KeyError as error:
                    raise ValueError(f"姓名牌角色无效：{name}") from error
        else:
            separator = pending_separator + token.separator
            body.append(_body_separator(separator, bool(body)))
            body.append(value)
            pending_separator = ""
            continue
        pending_separator += token.separator
    if background is None:
        raise ValueError("请指定一个背景短码")
    body_text = "".join(body).strip()
    if not body_text:
        raise ValueError("对话正文不能为空")
    return DialogueRequest(
        background=background,
        sprites=tuple(sprites),
        author=author,
        text=body_text,
    )
