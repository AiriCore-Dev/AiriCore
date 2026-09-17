import re

from .models import Character, Option
from .utils import CHARACTER_NAMES, get_character, get_statement


TRIAL_HELP = """用法：在同一条消息中发送
魔裁鸭梨 角色名
【疑问】这是一个疑问
【反驳】这是一个反驳

每行一个选项，支持 1～6 个选项，每项最多 300 字。
选项正文可用 \\n 换行，\\\\n 保留为字面量；选项之间仍用实际换行分隔。
类型：疑问、反驳、伪证、赞同、魔法:角色名。
例如：【魔法:艾玛】使用魔法
制作收费 10 积分。
角色名和魔法标签均支持角色简称或全名，例如 雪莉 或 橘雪莉。
回复魔裁审问生成图发送本指令，会在原图上加50%透明黑色，并靠右叠加人物和选项。
角色名可选：""" + "、".join(CHARACTER_NAMES)
OPTION_RE = re.compile(r"【(疑问|反驳|伪证|赞同|魔法)(?:[:：]([^】]*))?】(.*)")


def parse_trial(text: str) -> tuple[Character, list[Option]]:
    lines = text.strip().splitlines()
    if not lines:
        raise ValueError(TRIAL_HELP)
    name = lines[0].strip()
    try:
        character = get_character(name)
    except KeyError as error:
        raise ValueError(f"角色名 {name} 无效，请选择：{'、'.join(CHARACTER_NAMES)}") from error
    rows = [line.strip() for line in lines[1:] if line.strip()]
    if not 1 <= len(rows) <= 6:
        raise ValueError("请在角色名下方填写 1～6 行选项，每行使用【类型】正文格式")
    options = []
    for index, row in enumerate(rows, 1):
        match = OPTION_RE.fullmatch(row)
        if match is None:
            raise ValueError(f"第 {index} 个选项格式无效，请使用【疑问/反驳/伪证/赞同/魔法:角色名】正文")
        kind, argument, body = match.groups()
        if kind != "魔法" and argument is not None:
            raise ValueError(f"第 {index} 个选项只有魔法类型可以指定角色，请使用【{kind}】正文格式")
        body = re.sub(r"\\([\\n])", lambda match: "\n" if match[1] == "n" else "\\", body).strip()
        if not body or len(body) > 300:
            raise ValueError(f"第 {index} 个选项正文须为 1～300 字")
        try:
            statement = get_statement(kind, argument.strip() if argument else None)
        except KeyError as error:
            raise ValueError(f"第 {index} 个选项的魔法角色无效，请使用【魔法:角色名】格式") from error
        options.append(Option(statement, body))
    return character, options
