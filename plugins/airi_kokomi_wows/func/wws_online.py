import os
import cv2
import gc
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    call_api,
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
    # [lang]
    try:
        path = '/p/online-player/'
        params = {
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
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_online.png'), cv2.IMREAD_UNCHANGED)
    all_user = '{:,}'.format(result['data']['all']['online_players']).replace(',', ' ')
    text_list.append(
        Text_Data(
            xy=(187, 265),
            text=all_user,
            fill=(70,70,70),
            font_index=2,
            font_size=65
        )
    )
    i = 0
    fontStyle = fonts.data[2][65]
    for index in ['asia','eu','na','ru','cn']:
        online_player = '{:,}'.format(result['data'][index]['online_players']).replace(',', ' ')
        server_time = result['data'][index]['server_time']
        w = Picture.x_coord(server_time, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1040-w, 445+176*i),
                text=server_time,
                fill=(90,90,90),
                font_index=2,
                font_size=65
            )
        )
        w = Picture.x_coord(online_player, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1370-w, 445+176*i),
                text=online_player,
                fill=(70,70,70),
                font_index=2,
                font_size=65
            )
        )
        i += 1
    fontStyle = fonts.data[1][55]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(760-w/2, 1280),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=55
        )
    )
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    #res_img = res_img.resize((760, 685))
    return res_img


            


