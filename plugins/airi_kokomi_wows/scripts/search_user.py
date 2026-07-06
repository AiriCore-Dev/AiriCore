from ._api_helper import safe_call


async def search_user(
    server:str,
    nickname:str
) -> dict:
    parameter = [server,nickname]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/b/search-user/',
        params={
            'server':server,
            'nickname':nickname
        }
    )
