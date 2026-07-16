from ._base import program_error
import os
import time
import gc
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
    call_api,
    fonts,
    plugin_path
)

async def main(
    parameter: list,
) -> dict:
    result = await get_data(
        parameter=parameter
    )
    return result

async def get_data(
    parameter: list,
) -> dict:
    try:
        path = '/b/info-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'use_pr':parameter[3],
            'use_ac': parameter[4],
            'ac': parameter[5]
        }
        if parameter[4] is False:
            del params['use_ac']
            del params['ac']
        res = await call_api.call_api(
            params=params,
            path=path
        )
        if (
            res['status'] != 'ok' or
            res['message'] != 'SUCCESS'
        ):
            return res
        res_img = get_png(
            result=res,
            aid=parameter[0],
            server=parameter[1],
            lang=parameter[2]
        )
        result = {
            'status': 'ok',
            'message': 'SUCCESS',
            'img': None
        }
        result['img'] = Picture.return_img(img=res_img)
        del res_img
        return result
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()


def get_png(
    result: dict,
    aid: str,
    server: str,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_info.png'))
    res_img = Picture.resize(res_img, 0.8, 0.8)
    fontStyle = fonts.data[1][100]
    if result['data']['clans']['clan_tag'] == 'None':
        tag = '[]'
    else:
        tag = '['+str(result['data']['clans']['clan_tag'])+']'
    tag_color = Picture.hex_to_rgb(result['data']['clans']['clan_color'])
    text_list.append(
        Text_Data(
            xy=(160, 100),
            text=tag,
            fill=tag_color,
            font_index=1,
            font_size=100
        )
    )
    w = Picture.x_coord(tag, fontStyle)
    text_list.append(
        Text_Data(
            xy=(160+w+20, 100),
            text=result['nickname'],
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    id_w = w + Picture.x_coord(result['nickname'], fontStyle) + 40
    text_list.append(
        Text_Data(
            xy=(160+id_w, 95),
            text=str(result['data']['user']['karma']),
            fill=(0, 0, 0),
            font_index=1,
            font_size=35
        )
    )
    if lang == 'cn':
        server_dict = {
            'asia': '亚服 / ASIA',
            'eu': '欧服 / EU',
            'na': '美服 / NA',
            'ru': '俄服 / RU',
            'cn': '国服 / CN'
        }
        text_list.append(
            Text_Data(
                xy=(400, 420),
                text=server_dict[server],
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
    elif lang == 'en':
        server_dict = {
            'asia': 'Asia',
            'eu': 'Europe',
            'na': 'North America',
            'ru': 'Russia',
            'cn': 'China'
        }
        text_list.append(
            Text_Data(
                xy=(400, 420),
                text=server_dict[server],
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
    text_list.append(
        Text_Data(
            xy=(400, 500),
            text=str(aid),
            fill=(0, 0, 0),
            font_index=1,
            font_size=50
        )
    )
    creat_time = time.strftime(
        "%Y-%m-%d", time.localtime(result['data']['user']['created_at']))
    text_list.append(
        Text_Data(
            xy=(400, 580),
            text=creat_time,
            fill=(0, 0, 0),
            font_index=1,
            font_size=50
        )
    )
    active_time = time.strftime(
        "%Y-%m-%d", time.localtime(result['data']['user']['last_battle_time']))
    text_list.append(
        Text_Data(
            xy=(400, 660),
            text=active_time,
            fill=(0, 0, 0),
            font_index=1,
            font_size=50
        )
    )
    fontStyle = fonts.data[1][30]
    i = 0
    for index in ['pvp', 'rank', 'other']:
        temp_data = result['data']['battle_type'][index]
        text_list.append(
            Text_Data(
                xy=(120+478*i, 940),
                text=temp_data['battles_count'],
                fill=(0, 0, 0),
                font_index=2,
                font_size=80
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1070),
                text=temp_data['rate'],
                fill=(0, 0, 0),
                font_index=2,
                font_size=40
            )
        )
        if index == 'other':
            break
        str_pr = temp_data['avg_pr_des']
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(430+478*i-w/2, 817),
                text=str_pr,
                fill=(255, 255, 255),
                font_index=1,
                font_size=30
            )
        )
        box_list.append(
            Box_Data(
                xy=((364+478*i, 816), (499+478*i, 849)),
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
            )
        )
        box_list.append(
            Box_Data(
                xy=((80+478*i, 1395), (535+478*i, 1420)),
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1183),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(332+478*i, 1183),
                text=temp_data['avg_damage'],
                fill=Picture.hex_to_rgb(temp_data['avg_damage_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1286),
                text=temp_data['avg_frags'],
                fill=Picture.hex_to_rgb(temp_data['avg_frags_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(332+478*i, 1286),
                text=temp_data['avg_exp'],
                fill=(80, 80, 80),
                font_index=1,
                font_size=45
            )
        )
        i += 1
    i = 0
    y0 = 665
    for index in ['pvp_solo', 'pvp_div2', 'pvp_div3']:
        temp_data = result['data']['battle_type'][index]
        text_list.append(
            Text_Data(
                xy=(120+478*i, 940+y0),
                text=temp_data['battles_count'],
                fill=(0, 0, 0),
                font_index=2,
                font_size=80
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1070+y0),
                text=temp_data['rate'],
                fill=(0, 0, 0),
                font_index=2,
                font_size=40
            )
        )
        str_pr = temp_data['avg_pr_des']
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(430+478*i-w/2, 817+y0),
                text=str_pr,
                fill=(255, 255, 255),
                font_index=1,
                font_size=30
            )
        )
        box_list.append(
            Box_Data(
                xy=((364+478*i, 816+y0), (499+478*i, 849+y0)),
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
            )
        )
        box_list.append(
            Box_Data(
                xy=((80+478*i, 1395+y0), (535+478*i, 1420+y0)),
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1183+y0),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(332+478*i, 1183+y0),
                text=temp_data['avg_damage'],
                fill=Picture.hex_to_rgb(temp_data['avg_damage_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(120+478*i, 1286+y0),
                text=temp_data['avg_frags'],
                fill=Picture.hex_to_rgb(temp_data['avg_frags_color']),
                font_index=1,
                font_size=45
            )
        )
        text_list.append(
            Text_Data(
                xy=(332+478*i, 1286+y0),
                text=temp_data['avg_exp'],
                fill=(80, 80, 80),
                font_index=1,
                font_size=45
            )
        )
        i += 1
    index_list = result['data']['info'].values()
    fontStyle = fonts.data[1][50]
    i = 0
    for index in index_list:
        x = i % 4
        y = int(i / 4)
        w = Picture.x_coord(index, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1725+317.6*x-w/2, 417+100.8*y),
                text=index,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        i += 1
    i = 0
    for index in ['AirCarrier', 'Battleship', 'Cruiser', 'Destroyer', 'Submarine']:
        temp_data = result['data']['ship_type'][index]
        str_pr = '■ '+str(int(temp_data['avg_pr']))
        text_list.append(
            Text_Data(
                xy=(1836, 800+230*0.8*i),
                text=str_pr,
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color']),
                font_index=1,
                font_size=50
            )
        )
        text_list.append(
            Text_Data(
                xy=(1836, 868+230*0.8*i),
                text='占比:',
                fill=(74, 74, 74),
                font_index=1,
                font_size=40
            )
        )
        text_list.append(
            Text_Data(
                xy=(1836+105, 868+3+230*0.8*i),
                text=temp_data['rate'],
                fill=(0, 0, 0),
                font_index=2,
                font_size=50
            )
        )
        box_list.append(
            Box_Data(
                xy=((1532, 777+230*0.8*i), (1552, 937+230*0.8*i)),
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
            )
        )
        text_list.append(
            Text_Data(
                xy=(2940*0.8, 1000*0.8+230*0.8*i),
                text=temp_data['battles_count'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=40
            )
        )
        text_list.append(
            Text_Data(
                xy=(2940*0.8, 1083*0.8+230*0.8*i),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=40
            )
        )
        text_list.append(
            Text_Data(
                xy=(3218*0.8, 1000*0.8+230*0.8*i),
                text=temp_data['avg_damage'],
                fill=Picture.hex_to_rgb(temp_data['avg_damage_color']),
                font_index=1,
                font_size=40
            )
        )
        text_list.append(
            Text_Data(
                xy=(3218*0.8, 1083*0.8+230*0.8*i),
                text=temp_data['avg_frags'],
                fill=Picture.hex_to_rgb(temp_data['avg_frags_color']),
                font_index=1,
                font_size=40
            )
        )
        i += 1
    fontStyle1 = fonts.data[1][45]
    fontStyle2 = fonts.data[1][30]
    index_list = [
        'battles_count',
        'max_damage_dealt',
        'max_frags',
        'max_planes_killed',
        'max_exp',
        'max_total_agro',
        'max_scouting_damage'
    ]
    i = 0
    for record_index in index_list:
        j = 0
        for index in result['data']['record'][record_index]:
            ship_data = index['ship_data']
            ship_name = Game_Data.tier_dict[index['ship_info']['ship_tier']] + \
                '    '+index['ship_info']['ship_name']
            w = Picture.x_coord(ship_data, fontStyle1)
            text_list.append(
                Text_Data(
                    xy=(770-w/2+535*0.8*i, 2340+126*0.8*j),
                    text=ship_data,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=45
                )
            )
            w = Picture.x_coord(ship_name, fontStyle2)
            text_list.append(
                Text_Data(
                    xy=(770-w/2+535*0.8*i, 2392+126*0.8*j),
                    text=ship_name,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=30
                )
            )
            j += 1
        i += 1
    i = 0
    for index in result['data']['achievements']['battle']:
        x = i % 4
        y = int(i / 4)
        achievement_png_path = os.path.join(
            plugin_path, 'png', 'achievement', '{}.png'.format(index['name']))
        achievement_png = Picture.imread(
            achievement_png_path)
        achievement_png = Picture.resize(achievement_png, 1.4, 1.4)
        x1 = 2991+200*x
        y1 = 473+140*y
        x2 = x1 + achievement_png.shape[1]
        y2 = y1 + achievement_png.shape[0]
        res_img = Picture.merge_img(res_img, achievement_png, y1, y2, x1, x2)
        del achievement_png
        text_list.append(
            Text_Data(
                xy=(x1+100, y1+85),
                text='x'+str(index['count']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        i += 1
    i = 0
    for index in result['data']['achievements']['rank']:
        x = i % 4
        y = int(i / 4)
        achievement_png_path = os.path.join(
            plugin_path, 'png', 'achievement_plus', '{}.png'.format(index['name']))
        achievement_png = Picture.imread(
            achievement_png_path)
        achievement_png = Picture.resize(achievement_png, 1.4, 1.4)
        x1 = 2991+200*x
        y1 = 1394-160+135*y
        x2 = x1 + achievement_png.shape[1]
        y2 = y1 + achievement_png.shape[0]
        res_img = Picture.merge_img(res_img, achievement_png, y1, y2, x1, x2)
        del achievement_png
        text_list.append(
            Text_Data(
                xy=(x1+100, y1+85),
                text='x'+str(index['count']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        i += 1
    i = 0
    for index in result['data']['achievements']['cvc']:
        x = i % 4
        y = int(i / 4)
        achievement_png_path = os.path.join(
            plugin_path, 'png', 'achievement_plus', '{}.png'.format(index['name']))
        achievement_png = Picture.imread(
            achievement_png_path)
        achievement_png = Picture.resize(achievement_png, 1.4, 1.4)
        x1 = 2991+200*x
        y1 = 1596-160+135*y
        x2 = x1 + achievement_png.shape[1]
        y2 = y1 + achievement_png.shape[0]
        res_img = Picture.merge_img(res_img, achievement_png, y1, y2, x1, x2)
        del achievement_png
        if i <= 3:
            text_list.append(
                Text_Data(
                    xy=(x1+100, y1+85),
                    text='x'+str(index['count']),
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=35
                )
            )
        i += 1
    max_num = 0
    for tier, num in result['data']['ship_tier'].items():
        if num == {}:
            continue
        if num['battle_count'] >= max_num:
            max_num = num['battle_count']
    max_index = (int(max_num/100) + 1)*100
    i = 0
    fontStyle = fonts.data[1][25]
    for index in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']:
        temp_data = result['data']['ship_tier'][index]
        count = temp_data['battle_count']
        pic_len = 280-count/max_index*280
        x1 = int(2086*.8+89*0.8*i)
        y1 = int(2180*0.8+pic_len)
        x2 = int(2141*0.8+89*0.8*i)
        y2 = int(2528*0.8)
        w = Picture.x_coord(str(count), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1690-w/2+89*0.8*i, y1-30),
                text=str(count),
                fill=(0, 0, 0),
                font_index=1,
                font_size=25
            )
        )
        if pic_len < 279:
            box_list.append(
                Box_Data(
                    xy=((x1, y1), (x2, y2)),
                    fill=Picture.hex_to_rgb(temp_data['avg_pr_color'])
                )
            )
        i += 1
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    return res_img






