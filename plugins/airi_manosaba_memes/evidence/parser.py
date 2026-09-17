import re
from dataclasses import dataclass

from ..dialogue.parser import _body_separator, _tokens


ITEM_RE = re.compile(r'%WP[0-9]{3}', re.IGNORECASE)
TOKEN_RE = re.compile(r'''\s*((?:[^\s"'\\]|\\[\s\S]|"(?:[^"\\]|\\[\s\S])*"|'(?:[^'\\]|\\[\s\S])*')+)''')


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    item: str | None
    name: str
    description: str


def parse_evidence(text: str, image_count: int = 0) -> EvidenceRequest:
    if image_count not in (0, 1):
        raise ValueError('请只发送一张物品图片')
    if len(text) > 4000:
        raise ValueError('证物文字过长，请缩短后再生成')
    item = None
    name = None
    body = []
    pending_separator = ''
    position = 0
    while position < len(text.rstrip()):
        match = TOKEN_RE.match(text, position)
        if match is None:
            raise ValueError('文字引号没有闭合，或反斜线后缺少字符')
        raw = match.group(1)
        separator = text[position:match.start(1)]
        position = match.end()
        decoded = _tokens(raw)
        value = decoded[0].value if decoded else ''
        if raw.startswith('%'):
            if not ITEM_RE.fullmatch(value):
                raise ValueError(f'物品短码无效：{value}')
            if item is not None or image_count:
                raise ValueError('物品短码和图片只能选择一个，不能重复指定')
            item = value.upper()
        elif raw.startswith('*'):
            if name is not None:
                raise ValueError('只能指定一个证物名称')
            name = value[1:].strip()
            if not name or '\n' in name or '\r' in name:
                raise ValueError('证物名称不能为空或包含换行')
        else:
            body.append(_body_separator(pending_separator + separator, bool(body)))
            body.append(value)
            pending_separator = ''
            continue
        pending_separator += separator
    if item is None and not image_count:
        raise ValueError('请指定一个物品短码，或在同一条消息中发送一张图片')
    if name is None:
        raise ValueError('请使用 *名称 指定证物名称')
    description = ''.join(body).strip()
    if not description:
        raise ValueError('证物描述不能为空')
    return EvidenceRequest(item, name, description)
