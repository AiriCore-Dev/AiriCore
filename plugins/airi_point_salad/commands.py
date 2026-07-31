from dataclasses import dataclass
import re
from typing import Any

from .models import Character


ALIASES = {
    "root": {"沙拉", "salad", "sl"},
    "create": {"创建", "create", "cr"},
    "quick": {"快速", "quick", "qk"},
    "standard": {"标准", "standard", "std"},
    "classic": {"原版", "classic", "cl"},
    "mix": {"混合", "mix", "mx"},
    "join": {"加入", "join", "j"},
    "leave": {"退出", "leave", "lv"},
    "start": {"开始", "start", "st"},
    "take": {"拿", "take", "ta"},
    "flip": {"翻", "flip", "fl"},
    "skill": {"技能", "skill", "sk"},
    "board": {"桌面", "board", "bd"},
    "rules": {"规则", "rules", "rl"},
    "stop": {"结束", "stop", "sp"},
}


CHARACTER_ALIASES = {
    "minori": Character.MINORI,
    "实乃理": Character.MINORI,
    "花里实乃理": Character.MINORI,
    "haruka": Character.HARUKA,
    "遥": Character.HARUKA,
    "桐谷遥": Character.HARUKA,
    "airi": Character.AIRI,
    "桃井爱莉": Character.AIRI,
    "shizuku": Character.SHIZUKU,
    "雫": Character.SHIZUKU,
    "日野森雫": Character.SHIZUKU,
    "miku": Character.MIKU,
    "未来": Character.MIKU,
    "初音未来": Character.MIKU,
    "rin": Character.RIN,
    "铃": Character.RIN,
    "镜音铃": Character.RIN,
}


REVERSE_ALIASES = {
    alias.casefold(): name for name, aliases in ALIASES.items() for alias in aliases
}


@dataclass(frozen=True, slots=True)
class Command:
    action: str
    args: list[Any]


class CommandError(ValueError):
    pass


def parse_command(text: str) -> Command:
    tokens = text.strip().split()
    if not tokens or tokens[0].casefold() not in {item.casefold() for item in ALIASES["root"]}:
        raise CommandError("请使用 沙拉、salad 或 sl 开头")
    if len(tokens) == 1:
        return Command("rules", [])
    action = normalize(tokens[1])
    raw_args = tokens[2:]
    if action == "create":
        return parse_create(raw_args)
    if action == "take":
        return parse_take(raw_args)
    if action == "flip":
        return Command(action, [parse_index(raw_args, "sl fl 2")])
    if action == "skill":
        return Command(action, [parse_skill_arg(item) for item in raw_args])
    if action in {"join", "leave", "start", "board", "rules", "stop"}:
        if raw_args:
            raise CommandError(f"{tokens[1]} 不需要额外参数")
        return Command(action, [])
    raise CommandError("未知指令，请使用 sl rl 查看规则")


def normalize(token: str) -> str:
    return REVERSE_ALIASES.get(token.casefold(), token.casefold())


def parse_create(args: list[str]) -> Command:
    if len(args) != 2:
        raise CommandError("创建格式：sl cr qk cl")
    speed = normalize(args[0])
    mode = normalize(args[1])
    if speed not in {"quick", "standard"} or mode not in {"classic", "mix"}:
        raise CommandError("创建格式：sl cr qk cl")
    return Command("create", [speed, mode])


def parse_take(args: list[str]) -> Command:
    if not args:
        raise CommandError("拿牌格式：sl ta A 或 sl ta A1 B2")
    if len(args) == 1 and re.fullmatch(r"[abc]", args[0], re.IGNORECASE):
        return Command("take", [ord(args[0].upper()) - ord("A")])
    if (
        len(args) == 2
        and re.fullmatch(r"[abc]", args[0], re.IGNORECASE)
        and re.fullmatch(r"[abc][12]", args[1], re.IGNORECASE)
    ):
        return Command(
            "take",
            [ord(args[0].upper()) - ord("A"), parse_slot(args[1])],
        )
    try:
        slots = [parse_slot(item) for item in args]
    except CommandError:
        raise CommandError("拿牌格式：sl ta A 或 sl ta A1 B2") from None
    return Command("take", slots)


def parse_slot(token: str) -> tuple[int, int]:
    match = re.fullmatch(r"([abc])([12])", token, re.IGNORECASE)
    if not match:
        raise CommandError("角色牌位置应为 A1 至 C2")
    return ord(match.group(1).upper()) - ord("A"), int(match.group(2)) - 1


def parse_index(args: list[str], example: str) -> int:
    if len(args) != 1 or not args[0].isdigit() or int(args[0]) < 1:
        raise CommandError(f"编号格式：{example}")
    return int(args[0]) - 1


def parse_skill_arg(token: str) -> Any:
    if re.fullmatch(r"[abc][12]", token, re.IGNORECASE):
        return parse_slot(token)
    if re.fullmatch(r"[abc]", token, re.IGNORECASE):
        return ord(token.upper()) - ord("A")
    character = CHARACTER_ALIASES.get(token.casefold())
    if character is not None:
        return character
    if token.isdigit() and int(token) >= 1:
        return int(token) - 1
    raise CommandError("技能参数无效，请先发送 sl sk 查看示例")
