import gc
from .call_api import call_api
from .. import (
    write_error
)

async def get_clan_data(
    aid:str,
    server:str
) -> dict:
    # [aid server]
    parameter = [aid,server]
    try:
        path = '/b/user-clan/'
        params = {
            'aid':aid,
            'server':server
        }
        res = await call_api(
            params=params,
            path=path
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
