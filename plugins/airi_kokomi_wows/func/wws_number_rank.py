from ._base import program_error
import os
import cv2
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
    # [server lang ship_id]
    try:
        path = '/b/number-ship-rank/'
        params = {
            'server': parameter[0],
            'lang':parameter[1],
            'ship_id':parameter[2]
        }
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
            server=parameter[0],
            lang=parameter[1]
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
    server: str,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_server_rank.png'), cv2.IMREAD_UNCHANGED)
    ship_name = result['data']['ship_info']['ship_name']
    ship_tier = result['data']['ship_info']['ship_tier']
    ship_index = result['data']['ship_info']['ship_index']
    ship_nation = result['data']['ship_info']['ship_nation']
    ship_type = result['data']['ship_info']['ship_type']
    premium = result['data']['ship_info']['premium']
    special = result['data']['ship_info']['special']

    ship_name_str = Game_Data.tier_dict[ship_tier] + '    ' + ship_name + f'    ({server.upper()})'
    nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_index}.png')
    if os.path.exists(nation_png_path) is False:
        nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_nation}.png')
    if premium:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Premium.png')
    elif special:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Special.png')
    else:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Elite.png')

    fontStyle = fonts.data[1][70]
    w = Picture.x_coord(ship_name_str, fontStyle)
    all_len = 180+140+w
    text_list.append(
        Text_Data(
            xy=(all_len/2+1214-w, 151),
            text=ship_name_str,
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )

    nation_png = cv2.imread(nation_png_path, cv2.IMREAD_UNCHANGED)
    nation_png = cv2.resize(nation_png, None, fx=2, fy=2)
    x1 = int(1214-all_len/2)
    y1 = 129
    x2 = x1 + nation_png.shape[1]
    y2 = y1 + nation_png.shape[0]
    res_img = Picture.merge_img(res_img, nation_png, y1, y2, x1, x2)
    type_png = cv2.imread(type_png_path, cv2.IMREAD_UNCHANGED)
    x1 = int(1214-all_len/2+180)
    y1 = 142
    x2 = x1 + type_png.shape[1]
    y2 = y1 + type_png.shape[0]
    res_img = Picture.merge_img(res_img, type_png, y1, y2, x1, x2)
    fontStyle = fonts.data[1][30]
    i = 0
    for index in result['data']['rank']:
        nickname = index['nickname']
        if len(nickname) >= 28:
            nickname_str = nickname[:21] + ' ...'
        else:
            nickname_str = nickname
        rank_num = index['rank_num']
        x0 = 0
        y0 = 485
        w = Picture.x_coord(rank_num, fontStyle)
        text_list.append(
            Text_Data(
                xy=(168-w/2, y0 + 67*i),
                text=rank_num,
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        text_list.append(
            Text_Data(
                xy=(220, y0 + 67*i),
                text=nickname_str,
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['battles_count'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(792-w/2, y0 + 67*i),
                text=index['battles_count'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['personal_rating'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(919-w/2, y0 + 67*i),
                text=index['personal_rating'],
                fill=Picture.hex_to_rgb(index['avg_pr_color']),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['win_rate'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1041-w/2, y0 + 67*i),
                text=index['win_rate'],
                fill=Picture.hex_to_rgb(index['win_rate_color']),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['win_rate'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1041-w/2, y0 + 67*i),
                text=index['win_rate'],
                fill=Picture.hex_to_rgb(index['win_rate_color']),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['avg_frags'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1197-w/2, y0 + 67*i),
                text=index['avg_frags'],
                fill=Picture.hex_to_rgb(index['avg_frags_color']),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['avg_exp'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1360-w/2, y0 + 67*i),
                text=index['avg_exp'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['avg_damage'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1540-w/2, y0 + 67*i),
                text=index['avg_damage'],
                fill=Picture.hex_to_rgb(index['avg_damage_color']),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['max_frag'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1735-w/2, y0 + 67*i),
                text=index['max_frag'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['max_damage'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1949-w/2, y0 + 67*i),
                text=index['max_damage'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        w = Picture.x_coord(index['max_exp'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(2181-w/2, y0 + 67*i),
                text=index['max_exp'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=30
            )
        )
        i += 1

    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 3970),
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


            


