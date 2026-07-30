from ._base import program_error
import os
import gc
import json
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
    call_api,
    dog_tag,
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
        path = '/b/sx-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'use_ac': parameter[3],
            'ac': parameter[4]
        }
        if parameter[3] is False:
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
            lang=parameter[2],
            pic_num=1
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
    lang: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    if server == 'ru':
        res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_sx_lesta.png')
    else:
        res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_sx_wg.png')
    res_img = Picture.imread(res_img_path)
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=result['nickname'],
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    text_list.append(
        Text_Data(
            xy=(199, 275),
            text=f'{server.upper()} -- {aid}',
            fill=(80, 80, 80),
            font_index=1,
            font_size=45
        )
    )
    fontStyle = fonts.data[1][55]
    if result['data']['clans']['clan_tag'] != 'None':
        tag = '['+str(result['data']['clans']['clan_tag'])+']'
    else:
        tag = str(result['data']['clans']['clan_tag'])
    tag_color = Picture.hex_to_rgb(result['data']['clans']['clan_color'])
    if lang == 'cn':
        text_1 = '所属工会:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = '用户令牌:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        if result['data']['token'] == {}:
            box_list.append(
                Box_Data(
                    xy=(
                    (430,442),
                    (630,510)
                    ),
                    fill=(250,130,130)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(169+w_2+40, 448),
                    text='未授权',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
        else:
            box_list.append(
                Box_Data(
                    xy=(
                    (430,442),
                    (630,510)
                    ),
                    fill=(137,216,183)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(169+w_2+40, 448),
                    text='已授权',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
    elif lang == 'en':
        text_1 = 'User\'s Clan:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = 'Token:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag(res_img, aid, server, result['dog_tag'])
    fontStyle = fonts.data[1][70]
    if server == 'ru':
        sx_verson = '13.8版本扫雪(Lesta服)'
    else:
        sx_verson = '13.11版本扫雪(WG服)'
    w = Picture.x_coord(sx_verson, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 602),
            text=sx_verson,
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )
    if server == 'ru':
        all_card = 0
        all_ship = 0
        card_dict = {
            '11': 80,
            '10': 60,
            '9': 30,
            '8': 30,
            '7': 10,
            '6': 10,
            '5': 10
        }
        for tier in ['11','10','9','8','7','6','5']:
            all_card += result['data']['sx'][tier]*card_dict[tier]
            all_ship += result['data']['sx'][tier]
        all_card_str = '{:,}'.format(all_card).replace(',', ' ')
        all_ship_str = '{:,}'.format(all_ship).replace(',', ' ')
        fontStyle = fonts.data[2][110]
        w = Picture.x_coord(all_ship_str, fontStyle)
        text_list.append(
            Text_Data(
                xy=(322-w/2, 865),
                text=all_ship_str,
                fill=(0,0,0),
                font_index=2,
                font_size=110
            )
        )
        w = Picture.x_coord(all_card_str, fontStyle)
        text_list.append(
            Text_Data(
                xy=(785-w/2, 865),
                text=all_card_str,
                fill=(0,0,0),
                font_index=2,
                font_size=110
            )
        )
        i = 0
        for ship_tier_list in [['11'],['10'],['9','8'],['7','6','5']]:
            ship_number = 0
            ship_reward = card_dict[ship_tier_list[0]]
            for ship_tier in ship_tier_list:
                ship_number += result['data']['sx'][ship_tier]
            ship_reward_all = ship_number*ship_reward
            fontStyle = fonts.data[1][50]
            w = Picture.x_coord(str(ship_number), fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1523-w/2, 862+98*i),
                    text=str(ship_number),
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(str(ship_reward), fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1843-w/2, 862+98*i),
                    text=str(ship_reward),
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord('{:,}'.format(ship_reward_all).replace(',', ' '), fontStyle)
            text_list.append(
                Text_Data(
                    xy=(2164-w/2, 862+98*i),
                    text='{:,}'.format(ship_reward_all).replace(',', ' '),
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            i += 1
    else:
        all_card = 0
        all_coal = 0
        all_steel = 0

        coal_dict = {
            '5': 700,
            '6': 750,
            '7': 800
        }
        steel_dict = {
            '8': 70,
            '9': 80,
            '11': 200
        }
        for tier in ['7','6','5']:
            all_coal += result['data']['sx'][tier]*coal_dict[tier]
        for tier in ['11','9','8']:
            all_steel += result['data']['sx'][tier]*steel_dict[tier]
        all_card = result['data']['sx']['10']

        super_box = int(all_card/5)
        normal_box = all_card%5

        all_card_str = '{:,}'.format(all_card).replace(',', ' ')
        all_coal_str = '{:,}'.format(all_coal).replace(',', ' ')
        all_steel_str = '{:,}'.format(all_steel).replace(',', ' ')
        fontStyle = fonts.data[2][110]
        w = Picture.x_coord(all_steel_str, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w, 937),
                text=all_steel_str,
                fill=(0,0,0),
                font_index=2,
                font_size=110
            )
        )
        w = Picture.x_coord(all_coal_str, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w, 937+575),
                text=all_coal_str,
                fill=(0,0,0),
                font_index=2,
                font_size=110
            )
        )
        w = Picture.x_coord(all_card_str, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w, 937+575*2),
                text=all_card_str,
                fill=(0,0,0),
                font_index=2,
                font_size=110
            )
        )
        fontStyle = fonts.data[2][50]
        w = Picture.x_coord(str(result['data']['sx']['11']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1600-w, 1095),
                text=str(result['data']['sx']['11']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['9']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1900-w, 1095),
                text=str(result['data']['sx']['9']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['8']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2200-w, 1095),
                text=str(result['data']['sx']['8']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['7']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1600-w, 1095+575),
                text=str(result['data']['sx']['7']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['6']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1900-w, 1095+575),
                text=str(result['data']['sx']['6']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['5']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2200-w, 1095+575),
                text=str(result['data']['sx']['5']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        w = Picture.x_coord(str(result['data']['sx']['10']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w, 1095+575*2),
                text=str(result['data']['sx']['10']),
                fill=(0,0,0),
                font_index=2,
                font_size=50
            )
        )
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord('{:,}'.format(super_box).replace(',', ' '), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2110-w/2, 2716+160*0),
                text='{:,}'.format(super_box).replace(',', ' '),
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord('{:,}'.format(normal_box).replace(',', ' '), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2110-w/2, 2716+160*1),
                text='{:,}'.format(normal_box).replace(',', ' '),
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord('-', fontStyle)
        text_list.append(
            Text_Data(
                xy=(2110-w/2, 2716+160*2),
                text='-',
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    if server == 'ru':
        text_list.append(
            Text_Data(
                xy=(1214-w/2, 1265),
                text=Plugin_Config.BOT_INFO[lang],
                fill=(174, 174, 174),
                font_index=1,
                font_size=80
            )
        )
    else:
        text_list.append(
            Text_Data(
                xy=(1214-w/2, 3180),
                text=Plugin_Config.BOT_INFO[lang],
                fill=(174, 174, 174),
                font_index=1,
                font_size=80
            )
        )
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    return res_img
