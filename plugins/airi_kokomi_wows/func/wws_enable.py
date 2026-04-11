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
        gc.collect()
        return res
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


            


