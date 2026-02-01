import os
import base64
from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

def localpath_to_base64(pth):
    fil = open(pth,"rb")
    byt = fil.read()
    fil.close()
    return "base64://" + base64.b64encode(byt).decode() 

msg = []

text = "Momoi Airi 使用帮助\n⚙️ AiriCoreᵀᴹ v2.4.2"
msg.append({
    "type": "node",
    "data": {
        "name": "Momoi Airi",
        "uin": 0,
        "content":text
        }
    })  

text = "\
----- 音游类综合查询 -----\n\n\
- HarukiBot:\n\
PJSK综合查询 By NagiHina\n\
*发送指令 pjskhelp 查看帮助"
msg.append({
    "type": "node",
    "data": {
        "name": "音游类综合查询",
        "uin": 0,
        "content":text
        }
    })

text = "\
----- 战舰世界综合查询 -----\n\n\
- KokomiBot Airi Cust. Ver.:\n\
战舰世界水表查询 By Maoyu，Makino.S\n\
*使用 wws 触发\n\
*发送 wws help 查看帮助\n\n\
- HikariBot(yuyuko):\n\
战舰世界水表查询 By 西行寺雨季，本心\n\
*使用 yyk 触发\n\
*发送 yyk help 查看帮助"
msg.append({
    "type": "node",
    "data": {
        "name": "战舰世界综合查询",
        "uin": 0,
        "content":text
        }
    })

text = "\
----- MC服管 -----\n\n\
- Airi_MCRcon:\n\
Airi方可梦MC服务器管理插件 By Makino.S\n\
（此插件为<伊号公馆>群专属）\n\
*发送指令 /help 查看帮助"
msg.append({
    "type": "node",
    "data": {
        "name": "MC服管",
        "uin": 0,
        "content":text
        }
    })

text = "\
----- 娱乐功能 -----\n\n\
- Momoi Airi Collection:\n\
签到+收藏小游戏 By Makino.S\n\
*常用指令：签到\n\
*发送 签到帮助 查看帮助\n\n\
- Momoi Airi Wish Bottle:\n\
Airi心愿瓶（漂流瓶plus） By Makino.S\n\
*发送 心愿瓶帮助 查看帮助\n\n\
- Momoi Airi Turtle Soup:\n\
Airi海龟汤 By Makino.S\n\
*发送 海龟汤 查看帮助\n\n\
- 今日运势:\n\
测测你的今日运势\n\
*指令：jrys、今日运势\n\n\
- tarot:\n\
塔罗牌占卜 By MinatoAquaCrews\n\
*使用指令 占卜 触发\n\n\
- 今日老婆:\n\
随即抓取群友做老婆 By glamorgan9826\n\
*指令: jrlp、今日老婆\n\n\
- whateat-pic:\n\
今天吃什么 By Cvandia\n\
*常用指令: 今天吃什么，今天喝什么\n\n\
- Airi_choice:\n\
随机挑选插件 By Makino.S\n\
*发送 choicehelp 查看帮助\n\n\
- Simplemusic:\n\
点歌插件 By MeetWq\n\
*指令：点歌/qq点歌/网易点歌/酷我点歌/酷狗点歌/咪咕点歌/b站点歌 + 关键词\n\n\
- Memes:\n\
表情包制作 By MeetWq\n\
*发送 表情包制作 查看帮助\n\n\
- PJSK表情包制作:\n\
字面意思 By lgc-NB2Dev\n\
*发送 pjskbq 查看说明\n\n\
- emojimix:\n\
emoji合成\n\
*指令：任意emoji+任意emoji\n\
(需为系统自带的emoji而不是qq的emoji)\n\n\
- airi_roll: \n\
抽取随机数 By Makino.S\n\
*发送 roll help 查看帮助\n\n\
- ena_pjsk_score: \n\
烤倍率/pt计算器 By 咖啡不甜\n\
*指令：计算倍率，单人pt，协力pt，挑战pt"
msg.append({
    "type": "node",
    "data": {
        "name": "娱乐功能",
        "uin": 0,
        "content":text
        }
    })
    
text = "\
----- 棋类游戏 -----\n\n\
- chess:\n\
五子棋，黑白棋，围棋\n\
*开局指令：#五子棋，#黑白棋，#围棋\n\
*常用指令：#落子 坐标，#悔棋，#跳过回合，#停止下棋，#查看棋盘\n\
（由游戏发起人与第一个响应游戏的人组成先后手，其他人无法参与）\n\
（为和象棋插件区分，命令请使用英文#作为开头字符，如 #五子棋）\n\n\
- cchess:\n\
中国象棋\n\
*开局指令：@爱莉 象棋人机lvX(1-8) 或 @爱莉 象棋对战（人打人）\n\
*常用指令：炮二平五（中文格式），b2e2（坐标格式），结束下棋，显示棋盘\n\
悔棋（人机模式可无限悔棋；对战模式只能撤销自己上一手下的棋）\n\
（由游戏发起人与第一个响应游戏的人组成先后手，其他人无法参与）"
msg.append({
    "type": "node",
    "data": {
        "name": "Momoi Airi",
        "uin": 0,
        "content":text
        }
    })
    
text = "\
----- 基础插件 -----\n\n\
- analysis-bilibili:\n\
B站视频解析 By mengshouer\n\n\
- Airi-LLM:\n\
Airi智能体 By Makino.S\n\
*Airi会随机回复群内消息\n\n\
- Airi-Status:\n\
显示爱莉服务器状态 By Makino.S\n\
*发送 状态 显示\n\n\
- Airi-Help:\n\
显示此消息 By Makino.S\n\
*发送 帮助，help 显示"
msg.append({
    "type": "node",
    "data": {
        "name": "Momoi Airi",
        "uin": 0,
        "content":text
        }
    })
    
    
text = MessageSegment.text("\
===== 机器人原型介绍 =====\n\
Momoi Airi 桃井爱莉\n\
桃井爱莉（桃井 愛莉，ももい あいり）是《世界计划 彩色舞台 feat. 初音未来》（Project SEKAI, PJSK）及其衍生作品的登场角色。代表色为 #ffaacc。")
img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airi.png'))
image = MessageSegment.image(img)
msg.append({
    "type": "node",
    "data": {
        "name": "机器人原型介绍",
        "uin": 0,
        "content": text+image
        }
    })
    
text = MessageSegment.text("\
✨ Airi Cobblemon Server\n\
山河入画，萌兽为俦；静养初心，闲游忘忧\n\
这是一个基于整合包《去吧！方可梦大师》的Minecraft服务器，尽情和方块宝可梦游玩，成为最强训练家吧！\n\
整合包下载&服务器地址加群：740774974")
img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airicob.jpeg'))
image = MessageSegment.image(img)
msg.append({
    "type": "node",
    "data": {
        "name": "广告位",
        "uin": 0,
        "content": text+image
        }
    })
    
text = MessageSegment.text("\
Bot官群：\n\
*一群：1030569383\n\
*二群：808085026")
msg.append({
    "type": "node",
    "data": {
        "name": "广告位",
        "uin": 0,
        "content": text
        }
    })

text = MessageSegment.text("\
🛠️ AiriCore部分核心代码开源\n\
https://github.com/Tenma-Saki/AiriCore")
img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airocore.png'))
image = MessageSegment.image(img)
msg.append({
    "type": "node",
    "data": {
        "name": "广告位",
        "uin": 0,
        "content": text+image
        }
    })
    
text = MessageSegment.text("\
🕹️️ 如何搭建属于自己的Airi：\n\
https://www.airi.asia ")
img = localpath_to_base64(os.path.join(os.path.dirname(__file__), 'airiasia.jpg'))
image = MessageSegment.image(img)
msg.append({
    "type": "node",
    "data": {
        "name": "广告位",
        "uin": 0,
        "content": text+image
        }
    })


airi_help = on_fullmatch(("help","帮助"),priority=99)
@airi_help.handle()
async def main(bot: Bot, ev: MessageEvent):
    global msg
    for i in range(len(msg)):
        msg[i]["data"]["uin"] = bot.self_id
    if isinstance(ev, GroupMessageEvent):
        await bot.send_group_forward_msg(
            group_id=ev.group_id,
            messages=msg
        )
