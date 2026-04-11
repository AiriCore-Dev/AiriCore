import httpx
from httpx import (
    TimeoutException,
    ConnectTimeout,
    ReadTimeout
)
from ..data_source import Authorization
from ..config import Plugin_Config

async def call_api(
    path: str,
    params: dict,
    method: str = 'get'
) -> dict:
    try:
        base_url = Plugin_Config.API_URL + path
        if params == {}:
            url = '{}'.format(base_url)
        else:
            url = '{}?{}'.format(base_url, '&'.join(['{}={}'.format(key, value) for key, value in params.items()]))
        headers = {
            'accept': 'application/json',
            'Authorization': Authorization.get_authorization()
        }
        async with httpx.AsyncClient() as client:
            if method == 'get':
                res = await client.get(
                    url=url, 
                    headers=headers,
                    timeout=Plugin_Config.REQUEST_TIMEOUT
                )
            elif method == 'post':
                res = await client.post(
                    url=url, 
                    headers=headers,
                    timeout=Plugin_Config.REQUEST_TIMEOUT
                )
            request_code = res.status_code
            result = res.json()
        if request_code == 200:
            return result
        else:
            return {
                'status': 'error', 
                'message': 'NETWORK FAILURE', 
                'error': f'Request code:{res.status_code}'
            }
    except (
        TimeoutException, 
        ConnectTimeout, 
        ReadTimeout
    ):
        return {
            'status': 'error', 
            'message': 'NETWORK TIMEOUT', 
            'error': 'Request Timeout'
        }