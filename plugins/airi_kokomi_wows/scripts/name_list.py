import os
import cv2
import gc
from .wws_error import main as create_error_card
from .wws_message import main as return_message
from .. import (
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
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
    if result['status'] == 'error':
        result = create_error_card(result,parameter[0])
    if result['status'] == 'ok' and result['message'] == 'SUCCESS':
        return result
    else:
        lang = parameter[0]
        result = return_message(result,lang)
    return result

async def get_data(
    parameter: list,
) -> dict:
    # [lang data]
    try:
        res_img = get_png(
            result=parameter[1],
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
    result: list,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_ships_info2.png'), cv2.IMREAD_UNCHANGED)
    list_png_len = int(len(result) / 50) + 1
    list_img = cv2.imread(os.path.join(plugin_path, 'png', 'list', '80_50_2.png'), cv2.IMREAD_UNCHANGED)
    for i in range(list_png_len):
        res_img = cv2.vconcat([res_img, list_img])
    i = 0
    fontStyle = fonts.data[1][50]
    for ship_data in result:
        ship_tier = Game_Data.tier_dict[ship_data['ship_data']['tier']]
        ship_type = ship_data['ship_data']['type']
        w = Picture.x_coord(ship_tier,fontStyle)
        text_list.append(
            Text_Data(
                xy=(280-w/2, 417+90*i),
                text=ship_tier,
                fill=(0,0,0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(ship_type,fontStyle)
        text_list.append(
            Text_Data(
                xy=(504-w/2, 417+90*i),
                text=ship_type,
                fill=(0,0,0),
                font_index=1,
                font_size=50
            )
        )
        if lang == 'cn':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['cn'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
        elif lang == 'en':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text='-',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
        elif lang == 'ja':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['ja'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
        i += 1

    png_len = 407 + 90*i + 90
    box_list.append(
        Box_Data(
            xy=(
                (0,png_len-90),
                (1936,png_len-10)
            ),
            fill=(248,249,251)
        )
    )
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 1936, png_len))
    res_img = res_img.resize((968, int(png_len/2)))
    return res_img
