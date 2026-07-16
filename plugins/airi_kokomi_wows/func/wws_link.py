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
    try:
        path = '/b/add-bind/'
        params = {
            'platform':parameter[0],
            'uid':parameter[1],
            'aid': parameter[2],
            'server': parameter[3],
            'use_pr':parameter[4],
            'lang':parameter[5]
        }
        res = await call_api.call_api(
            params=params,
            path=path,
            method='post'
        )
        if (
            res['status'] != 'ok' or
            res['message'] != 'SUCCESS'
        ):
            return res
        result = res
        return result
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()