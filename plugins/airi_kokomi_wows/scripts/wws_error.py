import os
import time
from .. import (
    Plugin_Config,
    Picture,
    Text_Data
)
from .. import plugin_path

_ERROR_XY = {
    'cn': [(797, 820), (890, 876), (890, 930), (890, 985)],
    'en': [(815, 820), (930, 876), (891, 930), (1010, 985)],
    'ja': [(815, 820), (930, 876), (891, 930), (1010, 985)],
}


def main(
    result:dict,
    lang: str
) -> dict:
    if result['message'] in ['NETWORK FAILURE','NETWORK TIMEOUT']:
        error_type = 'network_error'
        error_data = [
            time.strftime("%Y-%m-%d %H:%M:%S UTC+8", time.localtime(time.time())),
            result['error'],
            'None',
            Plugin_Config.VERSON
        ]
    else:
        error_type = 'program_error'
        error_data = [
            time.strftime("%Y-%m-%d %H:%M:%S UTC+8", time.localtime(time.time())),
            result['error'],
            result['track_id'],
            Plugin_Config.VERSON
        ]
    res_img = get_png(
        lang=lang,
        error_type=error_type,
        error_data=error_data
    )
    result = {
        'status': 'ok',
        'message': 'SUCCESS',
        'img': None
    }
    result['img'] = Picture.return_img(img=res_img)

    return result

def get_png(lang:str,error_type:str,error_data:list):
    text_list = []
    png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', f'kokomi_{error_type}.png')
    res_img = Picture.imread(png_path)
    for xy, text in zip(_ERROR_XY[lang], error_data):
        text_list.append(
            Text_Data(
                xy=xy,
                text=text,
                fill=(75,75,75),
                font_index=1,
                font_size=45
            )
        )
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.resize((1480, 630))
    return res_img
