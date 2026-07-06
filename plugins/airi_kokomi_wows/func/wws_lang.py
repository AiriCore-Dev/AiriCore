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
    # [platform user_id lang]
    try:
        path = '/b/change-lang/'
        params = {
            'platform': parameter[0],
            'uid': parameter[1],
            'lang':parameter[2]
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


            


