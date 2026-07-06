from ._base import program_error
import gc
from .. import (
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
    # [aid server lang method class]
    try:
        if parameter[3] == 'recent':
            path = '/r1/enable-recent/'
            params = {
                'aid': parameter[0],
                'server': parameter[1],
                'recent_class':parameter[3]
            }
        else:
            path = '/r2/enable-recents/'
            params = {
                'aid': parameter[0],
                'server': parameter[1],
                'recents_class':parameter[3]
            }
        res = await call_api.call_api(
            params=params,
            path=path,
            method='post'
        )
        return res
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()


            


