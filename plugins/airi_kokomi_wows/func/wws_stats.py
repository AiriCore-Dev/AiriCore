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
    # [lang ship_id]
    try:
        path = '/p/ship-data/'
        params = {
            'lang':parameter[0],
            'ship_id':parameter[1]
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
            lang=parameter[0]
        )
        '''
        result = Picture.return_img(img=res_img)
        del res_img
        return result
        '''
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
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_ship_status.png'), cv2.IMREAD_UNCHANGED)

    ship_name = result['data']['ship_info']['ship_name']
    ship_tier = result['data']['ship_info']['ship_tier']
    ship_index = result['data']['ship_info']['ship_index']
    ship_nation = result['data']['ship_info']['ship_nation']
    ship_type = result['data']['ship_info']['ship_type']
    premium = result['data']['ship_info']['premium']
    special = result['data']['ship_info']['special']

    ship_name_str = Game_Data.tier_dict[ship_tier] + '    ' + ship_name
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
            xy=(all_len/2+1214-w, 322),
            text=ship_name_str,
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )

    nation_png = cv2.imread(nation_png_path, cv2.IMREAD_UNCHANGED)
    nation_png = cv2.resize(nation_png, None, fx=2, fy=2)
    x1 = int(1214-all_len/2)
    y1 = 310
    x2 = x1 + nation_png.shape[1]
    y2 = y1 + nation_png.shape[0]
    res_img = Picture.merge_img(res_img, nation_png, y1, y2, x1, x2)
    type_png = cv2.imread(type_png_path, cv2.IMREAD_UNCHANGED)
    x1 = int(1214-all_len/2+180)
    y1 = 323
    x2 = x1 + type_png.shape[1]
    y2 = y1 + type_png.shape[0]
    res_img = Picture.merge_img(res_img, type_png, y1, y2, x1, x2)
    
    x_list = [226,718,1090,1590,1920]
    i = 0
    for index in ['battles_count','win_rate','avg_damage','avg_frags','avg_exp']:
        text_list.append(
            Text_Data(
                xy=(x_list[i], 725),
                text=result['data']['total_data']['all'][index],
                fill=(0,0,0),
                font_index=2,
                font_size=80
            )
        )
        text_list.append(
            Text_Data(
                xy=(x_list[i]+170, 825),
                text=result['data']['total_data']['diff'][index],
                fill=Picture.hex_to_rgb(result['data']['total_data']['diff'][f'{index}_color']),
                font_index=1,
                font_size=40
            )
        )
        i += 1
    i = 0
    x0 = 0
    y0 = 1058
    fontStyle = fonts.data[1][55]
    for index in ['asia','eu','na','ru','cn']:
        w = Picture.x_coord(result['data']['total_data'][index]['battles_count'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(529-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['battles_count'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['win_rate'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(789-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['win_rate'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['avg_damage'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1103-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['avg_damage'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['avg_frags'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1380-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['avg_frags'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['avg_exp'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1630-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['avg_exp'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['avg_scouting_damage'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(2139-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['avg_scouting_damage'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(result['data']['total_data'][index]['avg_art_agro'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1869-w/2+x0, y0+90*i),
                text=result['data']['total_data'][index]['avg_art_agro'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
    i = 0
    x0 = 0
    y0 = 1744
    for index in ['asia','eu','na','ru','cn']:
        box_list.append(
            Box_Data(
                xy=(
                    (97,y0-10+90*i),
                    (435,y0-20+90*(i+1))
                ),
                fill=(223,224,226)
            )
        )
        server_dict = {
            'asia':'—亚服—',
            'eu':'—欧服—',
            'na':'—美服—',
            'ru':'—俄服—',
            'cn':'—国服—'
        }
        text_list.append(
            Text_Data(
                xy=(160, y0+90*i),
                text=server_dict[index],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
        for verson_data in result['data']['recent_data'][index]:
            text_list.append(
                Text_Data(
                    xy=(210, y0+90*i),
                    text=verson_data['verson'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['battles_count'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(529-w/2+x0, y0+90*i),
                    text=verson_data['battles_count'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['win_rate'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(809-w/2+x0, y0+90*i),
                    text=verson_data['win_rate'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['avg_damage'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1103-w/2+x0, y0+90*i),
                    text=verson_data['avg_damage'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['avg_frags'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1380-w/2+x0, y0+90*i),
                    text=verson_data['avg_frags'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['avg_exp'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1630-w/2+x0, y0+90*i),
                    text=verson_data['avg_exp'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['survived_rate'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1869-w/2+x0, y0+90*i),
                    text=verson_data['survived_rate'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(verson_data['avg_planes_killed'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(2139-w/2+x0, y0+90*i),
                    text=verson_data['avg_planes_killed'],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            i += 1
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 3450),
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


            


