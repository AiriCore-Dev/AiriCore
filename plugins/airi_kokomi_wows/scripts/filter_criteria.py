class Message_CN:
    tier_dict = {
        'T11': 11,
        'T10': 10,
        'T9': 9,
        'T8': 8,
        'T7': 7,
        'T6': 6,
        'T5': 5,
        'T4': 4,
        'T3': 3,
        'T2': 2,
        'T1': 1,
        '11': 11,
        '10': 10,
        '9': 9,
        '8': 8,
        '7': 7,
        '6': 6,
        '5': 5,
        '4': 4,
        '3': 3,
        '2': 2,
        '1': 1,
        '11级': 11,
        '10级': 10,
        '9级': 9,
        '8级': 8,
        '7级': 7,
        '6级': 6,
        '5级': 5,
        '4级': 4,
        '3级': 3,
        '2级': 2,
        '1级': 1,
        'XI': 11,
        'X': 10,
        'IX': 9,
        'VIII': 8,
        'VII': 7,
        'VI': 6,
        'V': 5,
        'IV': 4,
        'III': 3,
        'II': 2,
        'I': 1
    }
    type_dict = {
        'CV': 'AirCarrier',
        'BB': 'Battleship',
        'CA': 'Cruiser',
        'CL': 'Cruiser',
        'DD': 'Destroyer',
        'SS': 'Submarine',
        '航母': 'AirCarrier',
        '战列': 'Battleship',
        '巡洋': 'Cruiser',
        '驱逐': 'Destroyer',
        '潜艇': 'Submarine',
        '水下小人': 'Submarine',
        '空中小人': 'AirCarrier'
    }
    nation_dict = {
        'USA': 'usa',
        'M': 'usa',
        '美国': 'usa',
        '美系': 'usa',
        'M系': 'usa',
        'JAPAN': 'japan',
        'R': 'japan',
        '日本': 'japan',
        'R系': 'japan',
        '日系': 'japan',
        'EUROPE': 'europe',
        'E': 'europe',
        '欧洲': 'europe',
        'E系': 'europe',
        'FRANCE': 'france',
        'F': 'france',
        'F系': 'france',
        '法国': 'france',
        'GERMANY': 'germany',
        'D': 'germany',
        'D系': 'germany',
        '德国': 'germany',
        'UK': 'uk',
        'Y': 'uk',
        'Y系': 'uk',
        '英国': 'uk',
        'PANASIA': 'pan_asia',
        'C': 'pan_asia',
        'C系': 'pan_asia',
        '泛亚': 'pan_asia',
        '亚州': 'pan_asia',
        'USSR': 'ussr',
        'S': 'ussr',
        'S系': 'ussr',
        '苏联': 'ussr',
        'ITALY': 'italy',
        'I': 'italy',
        'I系': 'italy',
        '意大利': 'italy',
        'NETHERLANDS': 'netherlands',
        'HL': 'netherlands',
        'HL系': 'netherlands',
        '荷兰': 'netherlands',
        'PANAMERICA': 'pan_america',
        'FM': 'pan_america',
        'FM系': 'pan_america',
        '泛美': 'pan_america',
        'COMMONWEALTH': 'commonwealth',
        'CW': 'commonwealth',
        'CW系': 'commonwealth',
        '泛英': 'commonwealth',
        '英联邦': 'commonwealth',
        '联邦': 'commonwealth',
        'SPAIN': 'spain',
        'X': 'spain',
        'X系': 'spain',
        '西班牙': 'spain'
    }
    battle_dict = {
        'SOLO':'pvp_solo',
        'DIV2':'pvp_div2',
        'DIV3':'pvp_div3',
        '单野':'pvp_solo',
        '双排':'pvp_div2',
        '三排':'pvp_div3',
        '独轮车':'pvp_solo',
        '自行车':'pvp_div2',
        '三轮车':'pvp_div3'
    }
class Message_EN:
    tier_dict = {
        'T11': 11,
        'T10': 10,
        'T9': 9,
        'T8': 8,
        'T7': 7,
        'T6': 6,
        'T5': 5,
        'T4': 4,
        'T3': 3,
        'T2': 2,
        'T1': 1,
        '11': 11,
        '10': 10,
        '9': 9,
        '8': 8,
        '7': 7,
        '6': 6,
        '5': 5,
        '4': 4,
        '3': 3,
        '2': 2,
        '1': 1,
        'XI': 11,
        'X': 10,
        'IX': 9,
        'VIII': 8,
        'VII': 7,
        'VI': 6,
        'V': 5,
        'IV': 4,
        'III': 3,
        'II': 2,
        'I': 1
    }
    type_dict = {
        'CV': 'AirCarrier',
        'BB': 'Battleship',
        'CA': 'Cruiser',
        'CL': 'Cruiser',
        'DD': 'Destroyer',
        'SS': 'Submarine',
        'AIRCARRIER': 'AirCarrier',
        'BATTLESHIP': 'Battleship',
        'CRUISER': 'Cruiser',
        'DESTORYER': 'Destroyer',
        'SUBMARINE': 'Submarine',
        'SUB': 'Submarine'
    }
    nation_dict = {
        'USA': 'usa',
        'AMERICA': 'usa',
        'JAPAN': 'japan',
        'EUROPE': 'europe',
        'FRANCE': 'france',
        'GERMANY': 'germany',
        'UK': 'uk',
        'PANASIA': 'pan_asia',
        'USSR': 'ussr',
        'RUSSIA': 'ussr',
        'ITALY': 'italy',
        'NETHERLANDS': 'netherlands',
        'PANAMERICA': 'pan_america',
        'PANUSA': 'pan_america',
        'COMMONWEALTH': 'commonwealth',
        'SPAIN': 'spain'
    }
    battle_dict = {
        'SOLO':'pvp_solo',
        'DIV2':'pvp_div2',
        'DIV3':'pvp_div3'
    }
Message_JA = Message_EN

def main(
    lang: str,
    params: list
):
    ship_type = []
    ship_tier = []
    ship_nation = []
    battle_type = []
    non_zero = False
    non_old = False
    if lang == 'cn':
        message = Message_CN
    elif lang == 'en':
        message = Message_EN
    elif lang == 'ja':
        message = Message_JA
    for params_index in params:
        msg = params_index.upper()
        if '_' in msg:
            msg = msg.replace('_','')
        if msg in ['!0']:
            non_zero = True
        elif msg in ['!OLD']:
            non_old = True
        elif msg in message.tier_dict:
            tier = message.tier_dict[msg]
            if tier not in ship_tier:
                ship_tier.append(tier)
        elif msg in message.type_dict:
            type = message.type_dict[msg]
            if type not in ship_type:
                ship_type.append(type)
        elif msg in message.nation_dict:
            nation = message.nation_dict[msg]
            if nation not in ship_nation:
                ship_nation.append(nation)
        elif msg in message.battle_dict:
            battle = message.battle_dict[msg]
            if battle not in battle_type:
                battle_type.append(battle)
        else:
            return None
    return (
        non_zero,
        non_old,
        '' if ship_type == [] else list_to_str(ship_type),
        '' if ship_tier == [] else list_to_str(ship_tier),
        '' if ship_nation == [] else list_to_str(ship_nation),
        '' if battle_type == [] else list_to_str(battle_type)
    )

def list_to_str(
    data: list
):
    data_len = len(data)
    if data_len == 1:
        return data[0]
    else:
        data_str = data[0]
        for i in range(data_len-1):
            if i == data_len:
                break
            data_str = str(data_str) + f',{data[i+1]}'
        return data_str
