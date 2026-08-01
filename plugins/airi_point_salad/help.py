from .models import Character
from .skills import skill_usage


RULES_DOCUMENT_URL = "https://www.airi.asia/posts/aps_help/"


def help_sections() -> tuple[tuple[str, str], ...]:
    skill_lines = "；".join(
        f"{'Airi' if character is Character.AIRI else character.short_name}："
        f"{skill_usage(character)}"
        for character in Character
    )
    return (
        (
            "Airi-Point-Salad",
            "🥬 MORE MORE JUMP！得分沙拉\n摸摸酱们也要玩美式桌游！",
        ),
        (
            "官方基础与模式",
            "适合 2–6 人在群聊中游玩的 Point Salad 主题实现。普通模式使用官方基础规则；"
            "混合模式只在官方规则上加入一次性 Center 技能和公开 Live Mission。\n"
            "快速和标准只改变牌量：快速每种角色抽入人数 × 2 张，标准为人数 × 3 张；"
            "6 人标准局使用完整 108 张官方卡牌。\n"
            "桌面有三叠独立牌库，每列顶部是公开计分牌，下方两张角色牌只从同列补充。"
            "一叠清空时，从当前最大牌堆拆出下半部分建立新堆；最大堆并列时取较左一列。",
        ),
        (
            "指令列表",
            "所有指令必须以英文逗号 , 开头；英文命令不区分大小写。根命令：,沙拉 / ,salad / ,sl。\n"
            "创建：创建/create/cr + 快速/quick/qk 或 标准/standard/std + 原版/classic/cl 或 混合/mix/mx。示例：,sl cr qk mx。\n"
            "房间：加入/join/j（,sl j）、退出/leave/lv（,sl lv）、开始/start/st（,sl st）、结束/stop/sp（,sl sp）。\n"
            "行动：拿/take/ta；计分牌 ,sl ta A；角色牌 ,sl ta A1 B2；翻牌 ,sl fl 2。\n"
            f"混合模式技能：技能/skill/sk。{skill_lines}。实乃理完整三步示例："
            ",sl sk → ,sl ta A1 B2 → ,sl sk A1 C2。\n"
            "查看：桌面/board/bd（,sl bd）；规则/rules/rl（,sl rl）。",
        ),
        (
            "回合与官方计分",
            "每回合必须选择一项主行动：拿一张 A/B/C 列顶部计分牌，或拿两张 A1–C2 角色牌；"
            "残局不足两张角色牌时拿走全部。每列空位只从同列牌库补牌。\n"
            "每回合最多永久翻一张自己的计分牌。可以在主行动前翻，也可以在行动后、下一名玩家首次有效动作前翻，"
            "所以本回合刚拿到的计分牌也能翻面。查看桌面、查看帮助和失败操作不会关闭行动后窗口。\n"
            "十二类官方计分涵盖：最多、最少、奇偶、线性加减、同角色两张、同角色三张、指定组合、"
            "缺少种类、达到数量的种类、角色总数最少、角色总数最多、完整六种套组。比较类并列者都得分。",
        ),
        (
            "终局、扩展与文档",
            "三叠牌库与六个市场位置全部清空后结束。总分并列时，最后完成主行动的行动顺序较晚者排名更高。\n"
            "Center 和 Live Mission 仅在混合模式开放；Center 每局只能成功使用一次，Live Mission 每回合最多领取一项。\n"
            "大厅 15 分钟、对局 30 分钟内没有有效操作会自动关闭；查看桌面和帮助不会刷新计时。\n"
            f"完整图解玩法：{RULES_DOCUMENT_URL}",
        ),
        (
            "版权信息",
            "AiriCore 采用 MIT License\n"
            "Powered By AiriCore Dev.\n\n"
            "Point Salad 原作及 MORE MORE JUMP！、世界计划相关名称、角色与美术素材的权利归各自权利人所有。"
            "本插件为非官方同人实现，与原权利方无隶属或授权关系。",
        ),
    )
