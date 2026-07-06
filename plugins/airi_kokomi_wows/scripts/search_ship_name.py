from ._api_helper import safe_call
from .. import ship_side


async def search_ship_name(
    lang:str,
    shipname:str
) -> dict:
    parameter = [lang,shipname]
    try: shipname = ship_side.ship_side[shipname]
    except: pass
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/p/search-name/',
        params={
            'ship_name':shipname,
            'lang':lang
        }
    )
