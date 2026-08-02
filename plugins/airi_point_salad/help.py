from .models import Character
from .skills import skill_usage


RULES_DOCUMENT_URL = "https://www.airi.asia/posts/aps_help/"


def help_sections() -> tuple[tuple[str, str], ...]:
    skill_lines = "\n".join(
        f"    ·{character.short_name}举例："
        f"{skill_usage(character)}"
        for character in Character
    )
    return (
        (
            "Airi-Point-Salad",
            "🥬 MMJ得分沙拉\n摸摸酱们也要玩美式桌游！",
        ),
        (
            "游戏简介",
            "🍀 游戏简介\n"
            "这是一款适合 2–6 人在群聊中游玩的选牌桌游。\n"
            "玩家轮流拿取角色牌或计分牌，通过角色组合、翻牌规划和不同计分条件积累分数，最后总分最高者获胜。",
        ),
        (
            "指令列表",
            "📖 指令列表\n"
            "- 指令开头：,沙拉 / ,salad / ,sl\n"
            "- 创建房间：\n"
            "    创建/create/cr\n"
            "    快速/quick/qk 或 标准/standard/std\n"
            "    原版/classic/cl 或 混合/mix/mx\n"
            "    *示例：,sl cr qk mx\n"
            "- 房间操作：\n"
            "    加入/join/j\n"
            "    退出/leave/lv\n"
            "    开始/start/st\n"
            "    结束/stop/sp\n"
            "- 回合操作：\n"
            "    拿/take/ta\n"
            "     ·拿一张计分牌：,sl ta A\n"
            "     ·拿两张角色牌：,sl ta A1 B2\n"
            "    翻/flip/fl\n"
            "     ·示例：sl fl 2\n"
            "- Center 技能：\n"
            "    技能/skill/sk\n"
            f"{skill_lines}\n"
            "- 查看：\n"
            "    桌面/board/bd\n"
            "    规则/rules/rl"
        ),
        (
            "桌游玩法文档",
            "📚 桌游玩法文档\n"
            "网页版指南更加适合新手宝宝:\n"
            f"{RULES_DOCUMENT_URL}",
        ),
        (
            "版权信息",
            "AiriCore 采用 MIT License\n"
            "Powered By AiriCore Dev.\n"
            "Point Salad 原作及 MORE MORE JUMP！、世界计划相关名称、角色与美术素材的权利归各自权利人所有\n"
            "本插件为非官方同人实现，与原权利方无隶属或授权关系",
        ),
    )
