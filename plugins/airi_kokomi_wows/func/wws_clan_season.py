from ._base import program_error
import os
from PIL import Image
import gc
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Box_Data,
    call_api,
    clan_tag,
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
        path = '/b/clan-season-data/'
        params = {
            'server': parameter[1],
            'clan_id':parameter[0],
            'cvc_season': parameter[3],
            'lang':parameter[2]
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
            clan_id=parameter[0],
            cvc_season=parameter[3],
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
    clan_id: str,
    cvc_season: str,
    server: str,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_clan_season.png'))
    list_png_len = int(len(result['data']['members']) / 50) + 1
    list_img = Picture.imread(os.path.join(plugin_path, 'png', 'list', '60_50.png'))
    for i in range(list_png_len):
        res_img = Picture.vconcat([res_img, list_img])
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=str(result['data']['info']['tag']),
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    text_list.append(
        Text_Data(
            xy=(199, 275),
            text=f'{server.upper()} -- {clan_id}',
            fill=(80, 80, 80),
            font_index=1,
            font_size=45
        )
    )
    if lang == 'cn':
        text_list.append(
            Text_Data(
                xy=(466, 355),
                text=str(result['data']['info']['name']),
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_list.append(
            Text_Data(
                xy=(401, 355),
                text=str(result['data']['info']['name']),
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    if lang == 'cn':
        text_list.append(
            Text_Data(
                xy=(466, 445),
                text=f'第 {cvc_season} 赛季',
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_list.append(
            Text_Data(
                xy=(442, 445),
                text=f'{cvc_season} th',
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    res_img, text_list = clan_tag.clan_tag(res_img,text_list,result['data']['season']['leading_rating'])
    i = 0
    fontStyle = fonts.data[1][55]
    for index in ['1','2']:
        temp_data = result['data']['season']['teams'][index]
        w = Picture.x_coord(temp_data['rating_des'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(751-w/2, 810+90*i),
                text=temp_data['rating_des'],
                fill=Picture.hex_to_rgb(temp_data['rating_color']),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(temp_data['battles_count'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1160-w/2, 810+90*i),
                text=temp_data['battles_count'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(temp_data['win_rate'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1570-w/2, 810+90*i),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(temp_data['longest_winning_streak'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(2002-w/2, 810+90*i),
                text=temp_data['longest_winning_streak'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1

    res_img = Picture.cv2_to_pil(
        res_img=res_img
    ).convert('RGBA')
    role_dict = {
        '指挥官': 0,
        '副指挥官': 1,
        '征募官': 2,
        '现役军官': 3,
        '前线军官': 4,
        '军校见习生': 5,
        'Commander': 0,
        'Deputy Commander': 1,
        'Recruiter': 2,
        'Commissioned Officer': 3,
        'Line Officer': 4,
        'Midshipman': 5
    }
    clan_role_png_path = os.path.join(plugin_path,'png',f'bg_{lang}',f'clan_role.png')
    clan_role_png = Image.open(clan_role_png_path)
    i = 0
    fontStyle = fonts.data[1][35]
    for temp_data in result['data']['members']:
        role_id = role_dict.get(temp_data['role'],5)
        ship_png = clan_role_png.crop(((0), (0+60*role_id), (250), (60+60*role_id)))
        res_img.paste(ship_png, (139, 1205+70*i), mask = ship_png.split()[3])
        text_list.append(
            Text_Data(
                xy=(440, 1218+70*i),
                text=temp_data['nickname'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['battles_count'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1096-w/2, 1218+70*i),
                text=temp_data['battles_count'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['win_rate'], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1441-w/2, 1218+70*i),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['days_in_clan']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1790-w/2, 1218+70*i),
                text=str(temp_data['days_in_clan']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['last_battle_time']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2125-w/2, 1218+70*i),
                text=str(temp_data['last_battle_time']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        i += 1
    png_len = 1205 + 70*i + 130
    box_list.append(
        Box_Data(
            xy=(
                (0,png_len-130),
                (2428,png_len)
            ),
            fill=(248,249,251)
        )
    )
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, png_len-120),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=80
        )
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 2428, png_len))
    return res_img