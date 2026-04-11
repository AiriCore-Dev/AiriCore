import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    write_error,
    plugin_path
)

async def main(
    parameter: list,
) -> dict:
    if Plugin_Config.BOT_PLATFORM == 'discord' and parameter[0] == 'en':
        return {'status':'ok','message':'HELP'}
    else:
        result = await get_data(
            parameter=parameter
        )
    return result

async def get_data(
    parameter: list,
) -> dict:
    # [lang]
    try:
        res_img = get_png(
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
    lang: str
) -> str:
    help_png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_help.png')
    res_img = Image.open(help_png_path)
    ###res_img = res_img.resize((2640, 1376))
    return res_img