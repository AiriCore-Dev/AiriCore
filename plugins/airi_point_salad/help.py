RULES_DOCUMENT_URL = "https://example.com/airi-point-salad"


def help_sections() -> tuple[tuple[str, str], ...]:
    return (
        (
            "Airi-Point-Salad",
            "MORE MORE JUMP！得分沙拉\n摸摸酱们也要玩美式桌游！",
        ),
        (
            "游戏简介",
            "一款适合 2–6 人在群聊中游玩的选牌桌游。玩家轮流从市场取得角色牌或计分牌，"
            "通过角色组合、翻牌规划和不同计分条件积累分数，最后总分最高者获胜。",
        ),
        (
            "指令列表",
            "所有指令必须以英文逗号 , 开头；英文命令不区分大小写。根命令：,沙拉 / ,salad / ,sl。\n"
            "创建房间：创建/create/cr；局速：快速/quick/qk 或 标准/standard/std；模式：原版/classic/cl 或 混合/mix/mx。示例：,sl cr qk mx。\n"
            "房间操作：加入/join/j（,sl j）、退出/leave/lv（,sl lv）、开始/start/st（,sl st）、结束/stop/sp（,sl sp）。\n"
            "回合操作：拿/take/ta；拿一张计分牌：,sl ta A；拿两张角色牌：,sl ta A1 B2。翻/flip/fl：,sl fl 2。\n"
            "Center 技能：技能/skill/sk。实乃理：,sl sk，然后正常拿角色牌，再按提示交换；完整三步为 ,sl sk → ,sl ta A1 B2 → ,sl sk A1 B2。遥：,sl sk A；爱莉：,sl sk，然后使用 ,sl ta A A1；雫：,sl sk 2；未来：,sl sk 2 rin；铃：,sl sk A1 B2 C1。\n"
            "查看：桌面/board/bd（,sl bd）；规则/rules/rl（,sl rl）。",
        ),
        (
            "桌游玩法文档",
            "网页版玩法指南包含带注释的完整规则、回合流程、计分说明、Center 技能与 Live Mission 说明："
            f"{RULES_DOCUMENT_URL}\n"
            "该链接目前是部署占位地址，网站发布后请替换为正式 URL。",
        ),
        (
            "注意事项",
            "仅限群聊游玩，支持 2–6 名玩家；由房主开始，房主或群管理员可以结束对局。\n"
            "快速局每人 12 张牌，标准局每人 18 张牌。每回合拿牌前最多翻 1 张自己的计分牌；普通拿牌只能拿一张计分牌或两张角色牌，角色牌不足两张时必须拿走全部剩余角色牌。\n"
            "Center 和 Live Mission 仅在混合模式开放，并受各自每局与每回合限制。大厅 15 分钟、对局 30 分钟内没有有效操作会自动关闭；查看桌面和帮助不会刷新计时。",
        ),
        (
            "版权信息",
            "AiriCore 采用 MIT License\n"
            "Copyright (C) 2026 AiriCore Dev.\n\n"
            "Point Salad 原作及 MORE MORE JUMP！、世界计划相关名称、角色与美术素材的权利归各自权利人所有。"
            "本插件为非官方同人实现，与原权利方无隶属或授权关系。",
        ),
    )
