import os
import cv2
import gc
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Box_Data,
    call_api,
    clan_tag,
    write_error,
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
    # [clan_id server lang]
    try:
        path = '/b/clan-history-data/'
        params = {
            'server': parameter[1],
            'clan_id':parameter[0],
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
        gc.collect()
        return result
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        track_id = write_error(
            error_file=__file__,
            error_params=parameter,
            error_name=str(type(e).__name__),
            error_info=error_info
        )
        return {
            'status': 'error', 
            'message': 'PROGRAM ERROR', 
            'error':f'{str(type(e).__name__)}', 
            'track_id': f'{track_id}'
        }
    finally:
        gc.collect()


def get_png(
    result: dict,
    clan_id: str,
    server: str,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_clan_history.png'), cv2.IMREAD_UNCHANGED)
    list_png_len = int(len(result['data']['season'])*3 / 50) + 1
    list_img = cv2.imread(os.path.join(plugin_path, 'png', 'list', '80_50.png'), cv2.IMREAD_UNCHANGED)
    for i in range(list_png_len):
        res_img = cv2.vconcat([res_img, list_img])
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
                text=result['data']['info']['created_at'][:10],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_list.append(
            Text_Data(
                xy=(541, 445),
                text=result['data']['info']['created_at'][:10],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    i = 0
    fontStyle = fonts.data[1][55]
    for season_data in result['data']['season']:
        box_list.append(
            Box_Data(
                xy=(
                    (97,797+90*i),
                    (2331,877+90*i)
                ),
                fill=(222,223,225)
            )
        )
        if lang == 'cn':
            text_list.append(
                Text_Data(
                    xy=(161, 810+90*i),
                    text='第 {} 赛季 ({})'.format(season_data['cvc_season'],season_data['season_tier']),
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(season_data['season_time'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(2250-w, 810+90*i),
                    text=season_data['season_time'],
                    fill=(77,77,77),
                    font_index=1,
                    font_size=55
                )
            )
        else:
            text_list.append(
                Text_Data(
                    xy=(161, 810+90*i),
                    text='Season {}   ({})'.format(season_data['cvc_season'],season_data['season_tier']),
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
            w = Picture.x_coord(season_data['season_time'], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(2250-w, 810+90*i),
                    text=season_data['season_time'],
                    fill=(77,77,77),
                    font_index=1,
                    font_size=55
                )
            )
        i += 1
        for index in ['1','2']:
            team_dict = {
                '1': '-Alpha',
                '2': '-Bravo'
            }
            temp_data = season_data['teams'][index]
            w = Picture.x_coord(team_dict[index], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(286-w/2, 810+90*i),
                    text=team_dict[index],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=55
                )
            )
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
    )
    png_len = 797 + 90*i + 180
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
    #res_img = res_img.resize((1214, int(png_len/2)))
    return res_img