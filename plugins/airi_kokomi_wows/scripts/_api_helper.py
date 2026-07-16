import gc
import traceback
from .call_api import call_api
from .. import write_error


async def safe_call(
    *,
    error_file: str,
    error_params: list,
    path: str,
    params: dict,
    method: str = 'get',
    check_status: bool = True
) -> dict:
    try:
        res = await call_api(
            params=params,
            path=path,
            method=method
        )
        if check_status and (
            res['status'] != 'ok' or
            res['message'] != 'SUCCESS'
        ):
            return res
        result = res
        gc.collect()
        return result
    except Exception as e:
        error_info = traceback.format_exc()
        track_id = write_error(
            error_file=error_file,
            error_params=error_params,
            error_name=str(type(e).__name__),
            error_info=error_info
        )
        return {
            'status': 'error',
            'message': 'PROGRAM ERROR',
            'error': f'{str(type(e).__name__)}',
            'track_id': f'{track_id}'
        }
    finally:
        gc.collect()
