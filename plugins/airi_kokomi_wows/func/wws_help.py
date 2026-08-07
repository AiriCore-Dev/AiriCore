from ._base import program_error
import os
import gc
from utils import cache as asset_cache
from .. import (
    Plugin_Config,
    Picture,
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
        return result
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()


def get_png(
    lang: str
) -> str:
    help_png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_help.png')
    res_img = asset_cache.get_image(help_png_path)
    return res_img
