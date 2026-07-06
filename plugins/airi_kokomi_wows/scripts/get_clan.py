from ._api_helper import safe_call


async def get_clan_data(
    aid:str,
    server:str
) -> dict:
    # [aid server]
    parameter = [aid,server]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/b/user-clan/',
        params={
            'aid':aid,
            'server':server
        }
    )
