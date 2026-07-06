from ._api_helper import safe_call


async def get_bind_data(
    platform:str,
    uid:str
) -> dict:
    # [platform uid]
    parameter = [platform,uid]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/b/get-bind/',
        params={
            'platform':platform,
            'uid':uid
        }
    )
