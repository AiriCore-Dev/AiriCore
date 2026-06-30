import os
import base64

from nonebot import on_fullmatch, get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

PLUGIN_DIR = os.path.dirname(__file__)

driver = get_driver()
airicore_version = getattr(driver.config, "airicore_version", "")


def localpath_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return "base64://" + base64.b64encode(data).decode()


def image_segment(*path_parts: str) -> MessageSegment:
    """根据相对于插件目录的路径片段生成图片消息段。"""
    full_path = os.path.join(PLUGIN_DIR, *path_parts)
    return MessageSegment.image(localpath_to_base64(full_path))


def make_node(name: str, content) -> dict:
    """构造一个合并转发节点。"""
    return {
        "type": "node",
        "data": {
            "name": name,
            "uin": 0,
            "content": content,
        },
    }


# 合并转发的全部分区：增删某一节点只需增删对应的 make_node(...) 即可
msg = [
    make_node(
        "Momoi Airi",
        f"Momoi Airi 使用帮助\n⚙️ {airicore_version}"
        + image_segment("version", f"{airicore_version}.jpg"),
    ),
    make_node(
        "音游类综合查询",
        """----- 音游类综合查询 -----

- HarukiBot:
PJSK综合查询 By NagiHina
* 发送指令 pjskhelp 查看帮助""",
    ),
    make_node(
        "战舰世界综合查询",
        """----- 战舰世界综合查询 -----

- airi_kokomi_wows:
战舰世界水表查询 By Maoyu，AiriCore Dev.
* 使用 wws 触发
* 发送 wws help 查看帮助""",
    ),
    make_node(
        "Minecraft",
        """----- Minecraft -----

- Airi_MCRcon:
Airi Cobblemon Sever 服管 By AiriCore Dev.
（该功能仅对部分群聊开放）
* 发送指令 /help 查看帮助""",
    ),
    make_node(
        "娱乐功能",
        """----- 娱乐功能 -----

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

- 今日运势:
测测你的今日运势
* 指令：jrys、今日运势

- tarot:
塔罗牌占卜 By MinatoAquaCrews
* 使用指令 占卜 触发

- 今日老婆:
随即抓取群友做老婆 By glamorgan9826
* 指令: jrlp、今日老婆

- whateat-pic:
今天吃什么 By Cvandia
* 常用指令: 今天吃什么，今天喝什么

- Airi_choice:
随机挑选插件 By AiriCore Dev.
* 发送 choicehelp 查看帮助

- Memes:
表情包制作 By MeetWq
* 发送 表情包制作 查看帮助

- meme-stickers:
PJSK&Arcaea 贴纸制作 By lgc-NB2Dev
* 发送 pjskbq 或者 arcbq 查看说明

- emojimix:
emoji合成
* 指令：任意emoji+任意emoji
(需为系统自带的emoji而不是qq的emoji)

- airi_roll: 
抽取随机数 By AiriCore Dev.
* 发送 roll help 查看帮助

- ena_pjsk_score: 
烤倍率/pt计算器 By 咖啡不甜
* 指令：计算倍率，单人pt，协力pt，挑战pt

- Minesweeper:
扫雷游戏 By MeetWq
* 发送 扫雷帮助 查看帮助

- Airi_attrwhich:
英文缩写查询 By AiriCore Dev.
* 指令：xxx是什么""",
    ),
    make_node(
        "棋类游戏",
        """----- 棋类游戏 -----

- chess:
五子棋，黑白棋，围棋
* 开局指令：五子棋，黑白棋，围棋
* 常用指令：落子 坐标，悔棋，跳过回合，结束下棋，显示棋盘
（由游戏发起人与第一个响应游戏的人组成先后手，其他人无法参与）

- cchess:
中国象棋
* 开局指令：@爱莉 象棋人机lvX(1-8) 或 @爱莉 象棋对战（人打人）
* 常用指令：炮二平五（中文格式），b2e2（坐标格式），结束下棋，显示棋盘，
悔棋（人机模式可无限悔棋；对战模式只能撤销自己上一手下的棋）
（在PvP模式下，由游戏发起人与第一个响应游戏的人组成先后手，其他人无法参与）""",
    ),
    make_node(
        "基础插件",
        """----- 基础插件 -----

- Airi-LLM:
Airi智能体 By AiriCore Dev.
* Airi会随机回复群内消息
（该功能仅对直营姬开放）

- Airi-PackPic:
打包图片 By AiriCore Dev.
* 引用一条合并转发消息并发送 packpic 指令，压缩打包其中所有的图片

- Airi-Status:
显示爱莉服务器状态 By AiriCore Dev.
* 发送 状态 显示

- Airi-Help:
显示此消息 By AiriCore Dev.
* 发送 帮助，help 显示""",
    ),
    make_node(
        "机器人原型介绍",
        MessageSegment.text(
            """===== 机器人原型介绍 =====
Momoi Airi 桃井爱莉
桃井爱莉（桃井 愛莉，ももい あいり）是《世界计划 彩色舞台 feat. 初音未来》（Project SEKAI, PJSK）及其衍生作品的登场角色。代表色为 #ffaacc。"""
        )
        + image_segment("airi.png"),
    ),
    # ----- 已停用的广告位（Airi Cobblemon Server）-----
    # make_node(
    #     "广告位",
    #     MessageSegment.text(
    #         """✨ Airi Cobblemon Server
    # 山河入画，萌兽为俦；静养初心，闲游忘忧
    # 这是一个基于整合包《去吧！方可梦大师》的Minecraft服务器，尽情和方块宝可梦游玩，成为最强训练家吧！
    # 整合包下载&服务器地址加群：740774974"""
    #     )
    #     + image_segment("airicob.jpeg"),
    # ),
    make_node(
        "广告位",
        MessageSegment.text(
            """Bot使用群：
* 一群：1030569383
* 二群：808085026"""
        ),
    ),
    make_node(
        "广告位",
        MessageSegment.text(
            """🛠️ AiriCore代码开源
https://github.com/Tenma-Saki/AiriCore"""
        )
        + image_segment("airocore.png"),
    ),
    make_node(
        "广告位",
        MessageSegment.text(
            """🕹️️ AiriCore官方网站：
https://www.airi.asia """
        )
        + image_segment("airiasia.jpg"),
    ),
]


airi_help = on_fullmatch(("help", "帮助"), priority=99)


@airi_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    for node in msg:
        node["data"]["uin"] = bot.self_id
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_forward_msg(group_id=event.group_id, messages=msg)