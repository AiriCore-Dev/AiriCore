import gc
from .. import (
    call_api,
    write_error
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
    # [platform uid aid server user_pr lang]
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