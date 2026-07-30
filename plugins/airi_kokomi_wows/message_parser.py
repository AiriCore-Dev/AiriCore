from .config import Plugin_Config
from .kokomi_chs import trigger_list


def parse_to_command(msg: str):
    if 'wws bind cn ' in msg or 'wws bind 国服 ' in msg:
        split_msg = ['wws', 'bind', 'cn', msg[12:]]
    else:
        split_msg = msg.split()
    if not split_msg:
        return ('stop', None)
    if Plugin_Config.EN_START_WITH == split_msg[0]:
        del split_msg[0]
        if not split_msg:
            return ('stop', None)
    if Plugin_Config.EN_START_WITH == split_msg[0][0]:
        split_msg[0] = split_msg[0].replace(Plugin_Config.EN_START_WITH,'')
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
    if len(split_msg) > 1 and (split_msg[0]+' ' in trigger_list):
        split_msg[0] = 'wws'
    return ('dispatch', split_msg)
