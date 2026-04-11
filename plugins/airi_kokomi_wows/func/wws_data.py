import os
import cv2
import gc
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Box_Data,
    Game_Data,
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
    # [server lang ship_type ship_tier ship_nation]
    try:
        path = '/p/ships-data/'
        params = {
            'server': parameter[0],
            'ship_type': parameter[2],
            'ship_tier':parameter[3],
            'ship_nation': parameter[4]
        }
        if parameter[2] == '' or parameter[2] == None:
            del params['ship_type']
        if parameter[3] == '' or parameter[3] == None:
            del params['ship_tier']
        if parameter[4] == '' or parameter[4] == None:
            del params['ship_nation']
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
            lang=parameter[1],
            ship_type=[] if parameter[2] == '' else str(parameter[2]).split(','),
            ship_tier=[] if parameter[3] == '' else str(parameter[3]).split(','),
            ship_nation=[] if parameter[4] == '' else str(parameter[4]).split(',')
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
    server: str,
    lang: str,
    ship_type:list,
    ship_tier:list,
    ship_nation:list
) -> str:
    text_list = []
    box_list = []
    res_img = cv2.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_ships_data.png'), cv2.IMREAD_UNCHANGED)
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img = cv2.imread(os.path.join(plugin_path, 'png', 'list', '80_50.png'), cv2.IMREAD_UNCHANGED)
    for i in range(list_png_len):
        res_img = cv2.vconcat([res_img, list_img])
    fontStyle = fonts.data[1][55]
    filter_tier = str(ship_tier)
    filter_type = str(ship_type)
    filter_nation = str(ship_nation)
    filter_num = str(result['data']['data_num'])
    w = Picture.x_coord(server.upper(), fontStyle)
    text_list.append(
        Text_Data(
            xy=(328-w/2, 484),
            text=server.upper(),
            fill=(0, 0, 0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(filter_tier, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1660-w/2, 484),
            text=filter_tier,
            fill=(0, 0, 0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(filter_type, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 484),
            text=filter_type,
            fill=(0, 0, 0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(filter_nation, fontStyle)
    text_list.append(
        Text_Data(
            xy=(771-w/2, 484),
            text=filter_nation,
            fill=(0, 0, 0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(filter_num, fontStyle)
    text_list.append(
        Text_Data(
            xy=(2105-w/2, 484),
            text=filter_num,
            fill=(0, 0, 0),
            font_index=1,
            font_size=55
        )
    )
    i = 0
    fontStyle = fonts.data[1][50]
    for ship_data in result['data']['ships']:
        ship_tier = Game_Data.tier_dict[ship_data['ship_info']['tier']]
        ship_type = ship_data['ship_info']['type']
        w = Picture.x_coord(ship_data['ship_info']['ship_name'][lang], fontStyle)
        text_list.append(
            Text_Data(
                xy=(369-w/2, 829+90*i),
                text=ship_data['ship_info']['ship_name'][lang],
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(ship_tier, fontStyle)
        text_list.append(
            Text_Data(
                xy=(751-w/2, 829+90*i),
                text=ship_tier,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(ship_type, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1045-w/2, 829+90*i),
                text=ship_type,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(str(ship_data['ship_data']['win_rate']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1391-w/2, 829+90*i),
                text=str(ship_data['ship_data']['win_rate']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(str(ship_data['ship_data']['avg_damage']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(1737-w/2, 829+90*i),
                text=str(ship_data['ship_data']['avg_damage']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(str(ship_data['ship_data']['avg_frags']), fontStyle)
        text_list.append(
            Text_Data(
                xy=(2087-w/2, 829+90*i),
                text=str(ship_data['ship_data']['avg_frags']),
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        i += 1
    png_len = 817 + 90*i + 180
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
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 2428, png_len))
    #res_img = res_img.resize((1214, int(png_len/2)))
    return res_img


            


