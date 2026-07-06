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
    """统一封装 scripts 层 API 调用的 try/except/finally 样板。

    与原各文件逐行等价：
    - check_status=True 时，status!=ok 或 message!=SUCCESS 直接返回原始响应；
    - 异常时调 write_error 写日志并返回 PROGRAM ERROR；
    - finally 始终 gc.collect()。
    error_file 由调用方传入自身 __file__，保证错误日志归属不变。
    """
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
