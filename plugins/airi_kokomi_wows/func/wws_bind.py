from ._base import program_error
import os
import gc
from .. import (
    Plugin_Config,
    Picture,
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
        path = '/b/user-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
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
            aid=parameter[0],
            server=parameter[1],
            use_pr=parameter[5],
            lang=parameter[2],
            platform=parameter[3],
            platform_id=parameter[4]
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
    use_pr: bool,
    lang: str,
    platform: str,
    platform_id: str
) -> str:
    text_list = []
    box_list = []
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_bind.png'))

    fontStyle = fonts.data[1][55]
    w = Picture.x_coord(platform.upper(), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 415),
            text=platform.upper(),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(platform_id, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 560),
            text=platform_id,
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    if lang == 'cn':
        lang_info = '简体中文'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        lang_info = 'English'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        lang_info = '日本語'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )

    w = Picture.x_coord(str(aid), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1104),
            text=str(aid),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(server.upper(), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1249),
            text=server.upper(),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    nickname = result['data']['user']['nickname']
    w = Picture.x_coord(' ' if nickname is None else nickname, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1394),
            text=' ' if nickname is None else nickname,
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['user']['query_times']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1539),
            text=str(result['data']['user']['query_times']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['user']['cache_update_time']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1684),
            text=str(result['data']['user']['cache_update_time']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['class']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2083),
            text=str(result['data']['recent']['class']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['data_num']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2228),
            text=str(result['data']['recent']['data_num']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['start_date']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2373),
            text=str(result['data']['recent']['start_date']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    if lang == 'cn':
        recents_class = {
            0:'-',
            1:'官方接口-1（VIP）',
            2:'官方接口-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        recents_class = {
            0:'-',
            1:'Official API-1 (VIP)',
            2:'Official API-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        recents_class = {
            0:'-',
            1:'Official API-1 (VIP)',
            2:'Official API-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    on_png_path = os.path.join(plugin_path, 'png', 'list', 'on.png')
    on_png = Picture.imread(on_png_path)
    off_png_path = os.path.join(plugin_path, 'png', 'list', 'off.png')
    off_png = Picture.imread(off_png_path)
    if use_pr == True:
        x1 = 1430
        y1 = 817
        x2 = x1 + on_png.shape[1]
        y2 = y1 + on_png.shape[0]
        res_img = Picture.merge_img(res_img, on_png, y1, y2, x1, x2)
    else:
        x1 = 1430
        y1 = 817
        x2 = x1 + off_png.shape[1]
        y2 = y1 + off_png.shape[0]
        res_img = Picture.merge_img(res_img, off_png, y1, y2, x1, x2)
    if result['data']['recent']['enable'] == True:
        x1 = 1430
        y1 = 1905
        x2 = x1 + on_png.shape[1]
        y2 = y1 + on_png.shape[0]
        res_img = Picture.merge_img(res_img, on_png, y1, y2, x1, x2)
    else:
        x1 = 1430
        y1 = 1905
        x2 = x1 + off_png.shape[1]
        y2 = y1 + off_png.shape[0]
        res_img = Picture.merge_img(res_img, off_png, y1, y2, x1, x2)
    if result['data']['recents']['enable'] == True:
        x1 = 1430
        y1 = 2594
        x2 = x1 + on_png.shape[1]
        y2 = y1 + on_png.shape[0]
        res_img = Picture.merge_img(res_img, on_png, y1, y2, x1, x2)
    else:
        x1 = 1430
        y1 = 2594
        x2 = x1 + off_png.shape[1]
        y2 = y1 + off_png.shape[0]
        res_img = Picture.merge_img(res_img, off_png, y1, y2, x1, x2)
    del on_png
    del off_png
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(950-w/2, 2890),
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





