from ._base import program_error
import os
import time
import gc
from .. import (
    Plugin_Config,
    Picture,
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
        path = '/b/cw-data/'
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
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_cw.png'))
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img = Picture.imread(os.path.join(plugin_path, 'png', 'list', '80_50.png'))
    for i in range(list_png_len):
        res_img = Picture.vconcat([res_img, list_img])
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
        text_list.append(
            Text_Data(
                xy=(466, 355),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        creat_time = time.strftime(
            "%Y-%m-%d",
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(466, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_list.append(
            Text_Data(
                xy=(555, 355),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        creat_time = time.strftime(
            "%Y-%m-%d",
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(525, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        text_list.append(
            Text_Data(
                xy=(390, 355),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        creat_time = time.strftime(
            "%Y-%m-%d",
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(390, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag(res_img, aid, server, result['dog_tag'])
    if result['data']['achievements'] == {}:
        pass
    else:
        min_id = 4
        for ach_id, ach_num in result['data']['achievements'].items():
            ach_id = int(ach_id)
            if ach_id < min_id:
                min_id = ach_id
            text_list.append(
                Text_Data(
                    xy=(338+220*(4-ach_id), 810),
                    text=f'x{ach_num}',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=45
                )
            )
        cw_png_path = os.path.join(plugin_path, 'png', f'cw', '{}.png'.format(min_id))
        cw_png = Picture.imread(cw_png_path)
        x1 = 98
        y1 = 702
        x2 = x1 + cw_png.shape[1]
        y2 = y1 + cw_png.shape[0]
        res_img = Picture.merge_img(res_img, cw_png, y1, y2, x1, x2)
        del cw_png
    i = 0
    for index in result['data']['season']:
        x0 = 0
        y0 = 1158
        season_number = index['cvc_season']
        if lang == 'cn':
            season_number = f'第 {season_number} 赛季'
        elif lang == 'en':
            season_number = f'Season {season_number}'
        elif lang == 'ja':
            season_number = f'第 {season_number} シーズン'
        battles_count = index['battles_count']
        avg_win = index['win_rate']
        avg_damage = index['avg_damage']
        avg_frag = index['avg_frags']
        avg_xp = index['avg_exp']
        win_rate_color = Picture.hex_to_rgb(index['win_rate_color'])
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord(season_number, fontStyle)
        text_list.append(
            Text_Data(
                xy=(312-w/2+x0, y0+90*i),
                text=season_number,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(669-w/2+x0, y0+90*i),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1002-w/2+x0, y0+90*i),
                text=avg_win,
                fill=win_rate_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1365-w/2+x0, y0+90*i),
                text=avg_damage,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1753-w/2+x0, y0+90*i),
                text=avg_frag,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2091-w/2+x0, y0+90*i),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
    png_len = 1148 + 90*i + 180
    box_list.append(
        Box_Data(
            xy=(
                (0,png_len-180),
                (2428,png_len-10)
            ),
            fill=(248,249,251)
        )
    )
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, png_len-140),
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
    res_img = res_img.crop((0, 0, 2428, png_len))
    return res_img





