from ._base import program_error
import gc
import random
from .. import (
    Game_Data,
    call_api,
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
        path = '/p/ships-info/'
        params = {
            'ship_type': parameter[1],
            'ship_tier':parameter[2],
            'ship_nation': parameter[3]
        }
        if parameter[1] == '' or parameter[1] == None:
            del params['ship_type']
        if parameter[2] == '' or parameter[2] == None:
            del params['ship_tier']
        if parameter[3] == '' or parameter[3] == None:
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
            lang=parameter[0],
            ship_type=[] if parameter[1] == '' else str(parameter[1]).split(','),
            ship_tier=[] if parameter[2] == '' else str(parameter[2]).split(','),
            ship_nation=[] if parameter[3] == '' else str(parameter[3]).split(',')
        )
        result = {
            'status': 'info',
            'message': res_img
        }
        del res_img
        return result
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()


def get_png(
    result: dict,
    lang: str,
    ship_type:list,
    ship_tier:list,
    ship_nation:list
) -> str:
    ships = [
        ship for ship in result['data']['ships']
        if '（old）' not in ship['ship_info']['ship_name']['cn']
        and '(old)' not in ship['ship_info']['ship_name']['cn']
    ]
    if not ships:
        return '未找到符合条件的舰船' if lang == 'cn' else 'No matching ships found.'
    ship = random.choice(ships)
    text = ship['ship_info']['ship_name']['cn']
    tier_text = Game_Data.tier_dict[ship['ship_info']['tier']]
    type_text = ship['ship_info']['type']
    res_img = '{} {} {}'.format(tier_text, type_text, text)
    return res_img




