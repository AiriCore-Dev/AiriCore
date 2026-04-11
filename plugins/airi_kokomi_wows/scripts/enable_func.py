import gc
from .call_api import call_api
from .. import (
    write_error
)

async def enable_recent(
    parameter:list
) -> dict:
    # [method aid server recent_class]
    aid = parameter[0]
    server = parameter[1]
    recent_class = parameter[2]
    parameter = [aid,server,recent_class]
    try:
        path = '/r1/enable-recent/'
        params = {
            'aid':aid,
            'server':server,
            'recent_class':recent_class
        }
        res = await call_api(
            params=params,
            path=path,
            method='post'
        )
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

async def enable_recents(
    parameter:list
) -> dict:
    # [method aid server recents_class]
    aid = parameter[0]
    server = parameter[1]
    recents_class = parameter[2]
    parameter = [aid,server,recents_class]
    try:
        path = '/r2/enable-recents/'
        params = {
            'aid':aid,
            'server':server,
            'recents_class':recents_class
        }
        res = await call_api(
            params=params,
            path=path,
            method='post'
        )
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