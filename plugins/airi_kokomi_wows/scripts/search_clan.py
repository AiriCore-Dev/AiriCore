from ._api_helper import safe_call


async def search_clan(
    server:str,
    clan_tag:str
) -> dict:
    parameter = [server,clan_tag]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/b/search-clan/',
        params={
            'server':server,
            'clan_tag':clan_tag
        }
    )
