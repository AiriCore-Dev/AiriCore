from ._base import program_error
import os
import cv2
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
    # [aid server lang use_ac ac]
    try:
        path = '/b/oper-data/'
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
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_oper.png'), cv2.IMREAD_UNCHANGED)
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
        text_list.append(
            Text_Data(
                xy=(466, 445),
                text='剧情',
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
        text_list.append(
            Text_Data(
                xy=(525, 445),
                text='Operations',
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
    i = 0
    for index in ['oper_solo','oper_div','oper_div_hard']:
        temp_data = result['data']['oper_data'][index]
        battles_count = temp_data['battles_count']
        avg_win = temp_data['win_rate']
        avg_survival = temp_data['survival_rate']
        avg_survival_win = temp_data['survived_win_rate']
        max_star = temp_data['max_star_rate']
        avg_xp = temp_data['avg_exp']
        fontStyle = fonts.data[1][65]
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(290-w/2, 707+422*i),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(730-w/2, 707+422*i),
                text=avg_win,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        w = Picture.x_coord(max_star, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1170-w/2, 707+422*i),
                text=max_star,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(290-w/2, 820+422*i),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        w = Picture.x_coord(avg_survival, fontStyle)
        text_list.append(
            Text_Data(
                xy=(730-w/2, 820+422*i),
                text=avg_survival,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        w = Picture.x_coord(avg_survival_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1170-w/2, 820+422*i),
                text=avg_survival_win,
                fill=(0, 0, 0),
                font_index=1,
                font_size=65
            )
        )
        if result['data']['oper_data'][index]['stars'] == None:
            pass
        else:
            max_num = 100
            for stars_index in result['data']['oper_data'][index]['stars'].values():
                if stars_index > max_num:
                    max_num = stars_index
            fontStyle = fonts.data[1][35]
            for star_index in ['1','2','3','4','5']:
                star_num = 0 if star_index not in result['data']['oper_data'][index]['stars'] else result['data']['oper_data'][index]['stars'][star_index]
                star_len = int(star_num/max_num*150)+1
                box_list.append(
                    Box_Data(
                        xy=(
                            (1644+110*(int(star_index)-1),899-star_len+422*i),
                            (1699+110*(int(star_index)-1),899+422*i)
                        ),
                        fill=(162,217,255)
                    )
                )
                w = Picture.x_coord(str(star_num), fontStyle)
                text_list.append(
                    Text_Data(
                        xy=(1671+110*(int(star_index)-1)-w/2,899-star_len+422*i-40),
                        text=str(star_num),
                        fill=(70,70,70),
                        font_index=1,
                        font_size=35
                    )
                )
        i += 1
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 1860),
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


            


