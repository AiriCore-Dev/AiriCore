from .config import Plugin_Config
from .kokomi_chs import trigger_list


def parse_to_command(msg: str):
    """把（经 LLM 处理后的）消息字符串解析成分发用的 split_msg。

    与原 __init__.py 内联逻辑逐分支等价。返回 (action, payload)：
    - ('dispatch', split_msg): 交给 select_funtion 分发
    - ('stop', None):          静默结束（对应原来的裸 return）
    - ('reply', text):         回复一条文本后结束（对应原来的 bot.send + return）
    """
    # 国服id带空格的特殊处理
    if 'wws bind cn ' in msg or 'wws bind 国服 ' in msg:
        split_msg = ['wws', 'bind', 'cn', msg[12:]]
    else:
        split_msg = msg.split()  # 按空格分隔消息
    if Plugin_Config.EN_START_WITH == split_msg[0]:
        del split_msg[0]
    if Plugin_Config.EN_START_WITH == split_msg[0][0]:
        split_msg[0] = split_msg[0].replace(Plugin_Config.EN_START_WITH,'')
    # 快捷指令
    if split_msg[0][:6] == 'recent' and split_msg[0] != 'recents':
        if len(split_msg) == 1:
                if split_msg[0] == 'recent':
                    split_msg = ['wws', 'me', 'recent']
                else:
                    try: recent_days = int(split_msg[0][6:])
                    except: return ('stop', None)
                    else: split_msg = ['wws', 'me', 'recent', str(recent_days)]
        elif split_msg[1] in ['on','off','开','关'] and len(split_msg) == 2:
            split_msg_tmp = ['wws', 'recent']
            split_msg_tmp.append(split_msg[1])
            split_msg = split_msg_tmp
        else:
            try:
                int(split_msg[1])
            except:
                return ('reply', "recent天数错误！")
            if int(split_msg[1]) < 1:
                return ('reply', "recent天数错误！")
            split_msg_tmp = ['wws', 'me', 'recent']
            split_msg_tmp.append(split_msg[1])
            split_msg = split_msg_tmp
    elif split_msg[0][:4] == '看看我的':
        if len(split_msg) == 1:
            if split_msg[0] == '看看我的':
                return ('stop', None)
            split_msg_tmp = ['wws', 'me', 'ship']
            split_msg_tmp.append(split_msg[0][4:])
            split_msg = split_msg_tmp
        else:
            ship_name_tmp = split_msg[0][4:]
            for i in range(1,len(split_msg)):
                ship_name_tmp += split_msg[i]
            split_msg_tmp = ['wws', 'me', 'ship']
            split_msg_tmp.append(ship_name_tmp)
            split_msg = split_msg_tmp
    elif split_msg[0] == '绑定账号':
        if len(split_msg) != 3:
            return ('reply', "格式不正确！\n格式：绑定账号 服务器 ID")
        else:
            split_msg_tmp = ['wws', 'bind']
            split_msg_tmp.append(split_msg[1])
            split_msg_tmp.append(split_msg[2])
            split_msg = split_msg_tmp
    elif len(split_msg) == 1 and split_msg[0][0] != Plugin_Config.EN_START_WITH:
        if split_msg[0] == '看看我':
            split_msg = ['wws', 'me']
        elif split_msg[0] == '好好看看我':
            split_msg = ['wws', 'me', 'info']
        elif split_msg[0] == '查看全部战绩':
            split_msg = ['wws', 'me', 'ships', 'all']
        elif split_msg[0] == 'recents':
            split_msg = ['wws', 'me', 'recents']
        else:
            return ('stop', None)
    # 消息 -> 函数
    if len(split_msg) > 1 and (split_msg[0]+' ' in trigger_list):
        split_msg[0] = 'wws'
    return ('dispatch', split_msg)
