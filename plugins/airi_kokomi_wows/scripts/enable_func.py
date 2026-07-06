from ._api_helper import safe_call


async def enable_recent(
    parameter:list
) -> dict:
    # [method aid server recent_class]
    aid = parameter[0]
    server = parameter[1]
    recent_class = parameter[2]
    parameter = [aid,server,recent_class]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/r1/enable-recent/',
        params={
            'aid':aid,
            'server':server,
            'recent_class':recent_class
        },
        method='post',
        check_status=False
    )

async def enable_recents(
    parameter:list
) -> dict:
    # [method aid server recents_class]
    aid = parameter[0]
    server = parameter[1]
    recents_class = parameter[2]
    parameter = [aid,server,recents_class]
    return await safe_call(
        error_file=__file__,
        error_params=parameter,
        path='/r2/enable-recents/',
        params={
            'aid':aid,
            'server':server,
            'recents_class':recents_class
        },
        method='post',
        check_status=False
    )
