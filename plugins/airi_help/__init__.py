import copy
import os

from nonebot import on_fullmatch, get_driver, logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP

from utils.asset_cache import get_b64

PLUGIN_DIR = os.path.dirname(__file__)

driver = get_driver()
airicore_version = getattr(driver.config, "airicore_version", "")


def image_segment(*path_parts: str):
    full_path = os.path.join(PLUGIN_DIR, *path_parts)
    data = get_b64(full_path)
    if data is None:
        logger.warning(f"airi_help 图片缺失，已降级为纯文本: {full_path}")
        return ""
    return MessageSegment.image(data)


def version_node_content() -> object:
    head = f"Momoi Airi 使用帮助\n{airicore_version}"
    png = image_segment("version", f"{airicore_version}.jpg")
    return MessageSegment.text(head) + png if png else head


def make_node(name: str, content) -> dict:
    return {
        "type": "node",
        "data": {
            "name": name,
            "uin": 0,
            "content": content,
        },
    }

msg = [
    make_node(
        "Momoi Airi",
        version_node_content(),
    ),
    make_node(
        "音游类综合查询",
        """----- 音游类综合查询 -----

- HarukiBot:
PJSK综合查询 By NagiHina
* 发送指令 pjskhelp 查看帮助

- ena-pjsk-score:
烤倍率/pt计算器 By 咖啡不甜
* 指令：计算倍率，单人pt，协力pt，挑战pt""",
    ),
    make_node(
        "战舰世界综合查询",
        """----- 战舰世界综合查询 -----

- Airi-Kokomi-WoWS:
战舰世界水表查询 By Maoyu，AiriCore Dev.
* 使用 wws 触发
* 发送 wws help 查看帮助""",
    ),
    make_node(
        "Minecraft",
        """----- Minecraft -----

- Airi-MCRcon:
Airi Cobblemon Sever 服管 By AiriCore Dev.
（该功能仅对部分群聊开放）
* 发送指令 /help 查看帮助""",
    ),
    make_node(
        "娱乐插件",
        """----- 娱乐插件 -----

- Momoi Airi Collection:
签到+收藏小游戏 By AiriCore Dev.
* 常用指令：签到
* 发送 签到帮助 查看帮助

- Momoi Airi SEKAI Roguelike:
勇闯未知SEKAI小游戏 By AiriCore Dev.
* https://www.airi.asia/game
* 强烈建议使用外部浏览器游玩
（QQ自带浏览器登录较为困难）

- Momoi Airi Wish Bottle:
Airi心愿瓶（漂流瓶plus） By AiriCore Dev.
* 发送 心愿瓶帮助 查看帮助

- Momoi Airi Turtle Soup:
Airi海龟汤 By AiriCore Dev.
* 发送 海龟汤 查看帮助

- MORE MORE JUMP！Point Salad:
得分沙拉桌游 By AiriCore Dev.
* 发送 ,sl rl 查看玩法和完整指令

- jrys:
测测你的今日运势
* 指令：jrys

- tarot:
塔罗牌占卜 By MinatoAquaCrews
* 使用指令 占卜 触发

- today-waifu:
随即抓取群友做老婆 By glamorgan9826
* 指令: jrlp、hlp、强娶

- whateat-pic:
今天吃什么 By Cvandia
* 常用指令: 今天吃什么，今天喝什么

- Minesweeper:
扫雷游戏 By MeetWq
* 发送 扫雷帮助 查看帮助""",
    ),
    make_node(
        "功能插件",
        """----- 功能插件 -----

- Airi-Netease-Music:
网易云点歌 By AiriCore Dev.
* 指令：点歌 歌曲名

- Airi-Choice:
随机挑选插件 By AiriCore Dev.
* 发送 choicehelp 查看帮助

- Airi-Roll:
抽取随机数 By AiriCore Dev.
* 发送 roll help 查看帮助

- Airi-Attrwhich:
英文缩写查询 By AiriCore Dev.
* 指令：@Airi xxx是什么

- Airi-PackPic:
打包图片 By AiriCore Dev.
* 引用一条合并转发消息并发送 packpic 指令，压缩打包其中所有的图片

- Memes:
表情包制作 By MeetWq
* 发送 表情包制作 查看帮助

- meme-stickers:
PJSK&Arcaea 贴纸制作 By lgc-NB2Dev
* 发送 pjskbq 或者 arcbq 查看说明

- emojimix:
emoji合成
* 指令：任意emoji+任意emoji
(需为系统自带的emoji而不是qq的emoji)""",
    ),
    make_node(
        "棋类插件",
        """----- 棋类插件 -----

- chess:
五子棋，黑白棋，围棋（PvP only）
* 开局指令：五子棋，黑白棋，围棋
* 常用指令：落子 坐标，悔棋，跳过回合，结束下棋，显示棋盘

- cchess:
中国象棋（PvE & PvP）
* 开局指令：@Airi 象棋人机lvX，@Airi 象棋对战
* 落子指令：炮二平五（中文格式），b2e2（坐标格式）
* 其他指令：结束下棋，显示棋盘，悔棋""",
    ),
    make_node(
        "基础插件",
        """----- 基础插件 -----

- Airi-LLM:
Airi智能体 By AiriCore Dev.
* Airi会随机回复群内消息
（该功能仅对直营姬开放）

- Airi-Status:
显示AiriCore服务器状态 By AiriCore Dev.
* 发送 状态 显示

- Airi-Help:
显示此消息 By AiriCore Dev.
* 发送 帮助，help 显示""",
    ),
#    make_node(
#        "机器人原型介绍",
#        MessageSegment.text(
#            """===== 原型介绍 =====
#Momoi Airi 桃井爱莉
#桃井爱莉（桃井 愛莉，ももい あいり）是《世界计划 彩色舞台 feat. 初音未来》（Project SEKAI, PJSK）及其衍生作品的登场角色。代表色为 #ffaacc。"""
#        )
#        + image_segment("airi.png"),
#    ),
    make_node(
        "使用时间限制",
        """==== 使用时间限制 ====

**直营姬**休息时间：
23:00 - 次日6:00
期间无法使用大部分插件功能

请合理分配睡眠时间，保持健康作息""",
    ),
    make_node(
        "广告位",
        MessageSegment.text(
            """🕹️️ AiriCore官方网站：
https://www.airi.asia """
        )
        + image_segment("airiasia.jpg"),
    ),
    make_node(
        "广告位",
        MessageSegment.text(
            """* Bot一群：1030569383
* Bot二群：808085026
* 分布式交流群：1084667424"""
        ),
    ),
    make_node(
        "广告位",
        MessageSegment.text(
            """🛠️ AiriCore代码开源
https://github.com/AiriCore-Dev/AiriCore"""
        )
        + image_segment("airocore.png"),
    ),
]


Airi_help = on_fullmatch(("help", "帮助"), priority=99, permission=GROUP)


@Airi_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await Airi_help.finish("帮助只能在群聊内查看哦~")
    nodes = copy.deepcopy(msg)
    for node in nodes:
        node["data"]["uin"] = bot.self_id
    await bot.send_group_forward_msg(group_id=event.group_id, messages=nodes)
