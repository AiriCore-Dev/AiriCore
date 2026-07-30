from .data_source import Message, SafeMessage
from .log.error_log import write_error
from .scripts import (
    get_clan,
    name_list,
    search_user,
    search_clan,
    search_ship_name,
    filter_criteria,
    time_zone,
    enable_func
)
from .func import (
    wws_bind,
    wws_clan_info,
    wws_link,
    wws_basic,
    wws_info,
    wws_rank,
    wws_cw,
    wws_oper,
    wws_online,
    wws_ship,
    wws_ship_recent,
    wws_recent,
    wws_me_rank,
    wws_number_rank,
    wws_rank_season,
    wws_ships,
    wws_help,
    wws_lang,
    wws_pr,
    wws_clan_season,
    wws_clan_history,
    wws_name,
    wws_data
)

async def main(
    msg:list,
    user_id:str,
    user_data:dict,
    platform:str,
    platform_id:str,
    channel_id:str,
    platform_data:dict,

    aid:str,
    server:str,
    use_pr:bool,
    lang:str,
    use_ac:bool,
    ac:str
):
    msg = SafeMessage(msg)
    parameter = []
    try:
        params_error_msg = {'status':'ok','message':'PARAMS ERROR'}
        func_not_found_msg = {'status':'ok','message':'FUNC NOT FOUND'}
        if (
            len(msg) == 1 and
            msg[0] in ['help']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_help.main,
                'parameter':[
                    lang
                ]
            }
        if (
            len(msg) == 3 and
            msg[0] in ['link']
        ):
            server = Message.server_dict.get(msg[1],None)
            if server is None:
                return params_error_msg
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[2]
            )
            if (
                nickname['status'] != 'ok' or
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_link.main,
                'parameter':[
                    platform,
                    user_id,
                    aid,
                    server,
                    use_pr,
                    lang
                ]
            }
        if aid == None:
            return {'status':'ok','message':'NO BIND DATA'}
        if (
            len(msg) == 1 and
            msg[0] in ['me']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_basic.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 1 and
            msg[0] in ['rank']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_rank.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 1 and
            msg[0] in ['bind']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_bind.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    platform,
                    user_id,
                    use_pr
                ]
            }
        if (
            len(msg) == 3 and
            msg[0] in ['set'] and
            msg[1] in ['pr'] and
            msg[2] in ['on','off']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_pr.main,
                'parameter':[
                    platform,
                    user_id,
                    lang,
                    True if msg[2] == 'on' else False
                ]
            }
        if (
            len(msg) == 3 and
            msg[0] in ['set'] and
            msg[1] in ['lang'] and
            msg[2] in ['cn','en']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_lang.main,
                'parameter':[
                    platform,
                    user_id,
                    msg[2]
                ]
            }
        if (
            len(msg) == 3 and
            msg[0] in ['set'] and
            msg[1] in ['recent','recents'] and
            msg[2] in ['on','off']
        ):
            if msg[2] in ['off']:
                return {'status':'ok','message':'PLEASE CONNECT AUTHOR'}
            if msg[1] in ['recent']:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':enable_func.enable_recent,
                    'parameter':[
                        aid,
                        server,
                        400
                    ]
                }
            elif msg[1] in ['recents']:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':enable_func.enable_recents,
                    'parameter':[
                        aid,
                        server,
                        1
                    ]
                }
        if (
            len(msg) == 2 and
            msg[0] in ['rank'] and
            (msg[1].lower()).startswith('s')
        ):
            rank_season = (msg[1].lower()).replace('s','')
            try:
                rank_season = int(rank_season)
            except:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_rank_season.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    rank_season,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 1 and
            msg[0] in ['oper']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_oper.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        if (
            msg[0] in ['cw']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_cw.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) >= 2 and
            msg[0] in ['ship'] and
            not (len(msg) >= 3 and msg[2] in ['recent', 'rank'])
        ):
            if len(msg) == 2:
                ship_name = msg[1]
            else:
                name_tmp = ''
                for i in msg[1:]:
                    name_tmp += i
                ship_name = name_tmp
            shipid = await search_ship_name.search_ship_name(
                lang=lang,
                shipname=ship_name
            )
            if (
                shipid['status'] != 'ok' or
                shipid['message'] != 'SUCCESS'
            ):
                return shipid
            if shipid['data']['data_num'] == 0:
                return {'status':'ok','message':'NAME NOT FOUND'}
            if shipid['data']['data_num'] > 2:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':name_list.main,
                    'parameter':[
                        lang,
                        shipid['data']['ships']
                    ]
                }
            shipid = shipid['data']['ships'][0]['ship_id']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_ship.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    shipid,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) >= 2 and
            msg[0] in ['ships']
        ):
            if len(msg) == 2 and msg[1] in ['all']:
                msg = ['ships','ss','dd','ca','bb','cv']
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[1:]
            )
            if filter_data is None:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_ships.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    filter_data[0],
                    filter_data[1],
                    filter_data[2],
                    filter_data[3],
                    filter_data[4],
                    filter_data[5],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) <= 2 and
            msg[0] in ['recent']
        ):
            if len(msg) == 1:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[1]) == 17 and msg[1][8] in ['~','-']:
                    date_1 = msg[1][:8]
                    date_2 = msg[1][9:]
                    date_1_int = time_zone.date_to_timestamp(date_1)
                    date_2_int = time_zone.date_to_timestamp(date_2)
                    if (
                        date_1_int is None or
                        date_2_int is None
                    ):
                        return params_error_msg
                    if (
                        date_1_int >= date_2_int or
                        date_1 == date_2
                    ):
                        return params_error_msg
                    time_data = (
                        date_1,
                        date_2
                    )
                else:
                    try:
                        date_num = int(msg[1])
                    except:
                        return params_error_msg
                    time_data = time_zone.get_str_server_time(
                        server=server,
                        date_num=date_num
                    )
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_recent.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    'pvp',
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) <= 3 and
            msg[0] in ['pvp','rank'] and
            msg[1] in ['recent']
        ):
            if len(msg) == 2:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[2]) == 17 and msg[2][8] in ['~','-']:
                    date_1 = msg[2][:8]
                    date_2 = msg[2][9:]
                    date_1_int = time_zone.date_to_timestamp(date_1)
                    date_2_int = time_zone.date_to_timestamp(date_2)
                    if (
                        date_1_int is None or
                        date_2_int is None
                    ):
                        return params_error_msg
                    if (
                        date_1_int >= date_2_int or
                        date_1 == date_2
                    ):
                        return params_error_msg
                    time_data = (
                        date_1,
                        date_2
                    )
                else:
                    try:
                        date_num = int(msg[2])
                    except:
                        return params_error_msg
                    time_data = time_zone.get_str_server_time(
                        server=server,
                        date_num=date_num
                    )
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_recent.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    msg[0],
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) <= 4 and
            msg[0] in ['ship'] and
            msg[2] in ['recent']
        ):
            ship_name = msg[1]
            shipid = await search_ship_name.search_ship_name(
                lang=lang,
                shipname=ship_name
            )
            if (
                shipid['status'] != 'ok' or
                shipid['message'] != 'SUCCESS'
            ):
                return shipid
            if shipid['data']['data_num'] == 0:
                return {'status':'ok','message':'NAME NOT FOUND'}
            if shipid['data']['data_num'] > 2:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':name_list.main,
                    'parameter':[
                        lang,
                        shipid['data']['ships']
                    ]
                }
            shipid = shipid['data']['ships'][0]['ship_id']
            if len(msg) == 3:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[3]) == 17 and msg[3][8] in ['~','-']:
                    date_1 = msg[3][:8]
                    date_2 = msg[3][9:]
                    date_1_int = time_zone.date_to_timestamp(date_1)
                    date_2_int = time_zone.date_to_timestamp(date_2)
                    if (
                        date_1_int is None or
                        date_2_int is None
                    ):
                        return params_error_msg
                    if (
                        date_1_int >= date_2_int or
                        date_1 == date_2
                    ):
                        return params_error_msg
                    time_data = (
                        date_1,
                        date_2
                    )
                else:
                    try:
                        date_num = int(msg[3])
                    except:
                        return params_error_msg
                    time_data = time_zone.get_str_server_time(
                        server=server,
                        date_num=date_num
                    )
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_ship_recent.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    shipid,
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 3 and
            msg[0] in ['ship'] and
            msg[2] in ['rank']
        ):
            ship_name = msg[1]
            shipid = await search_ship_name.search_ship_name(
                lang=lang,
                shipname=ship_name
            )
            if (
                shipid['status'] != 'ok' or
                shipid['message'] != 'SUCCESS'
            ):
                return shipid
            if shipid['data']['data_num'] == 0:
                return {'status':'ok','message':'NAME NOT FOUND'}
            if shipid['data']['data_num'] > 2:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':name_list.main,
                    'parameter':[
                        lang,
                        shipid['data']['ships']
                    ]
                }
            shipid = shipid['data']['ships'][0]['ship_id']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_me_rank.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    shipid,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 4 and
            Message.server_dict.get(msg[0],None) != None and
            msg[1] in ['ship'] and
            msg[3] in ['rank']
        ):
            server = Message.server_dict.get(msg[0],None)
            if server is None:
                return params_error_msg
            ship_name = msg[2]
            shipid = await search_ship_name.search_ship_name(
                lang=lang,
                shipname=ship_name
            )
            if (
                shipid['status'] != 'ok' or
                shipid['message'] != 'SUCCESS'
            ):
                return shipid
            if shipid['data']['data_num'] == 0:
                return {'status':'ok','message':'NAME NOT FOUND'}
            if shipid['data']['data_num'] > 2:
                return {
                    'status':'ok',
                    'message':'SUCCESS',
                    'function':name_list.main,
                    'parameter':[
                        lang,
                        shipid['data']['ships']
                    ]
                }
            shipid = shipid['data']['ships'][0]['ship_id']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_number_rank.main,
                'parameter':[
                    server,
                    lang,
                    shipid
                ]
            }
        if (
            msg[0] in ['online']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_online.main,
                'parameter':[
                    lang
                ]
            }
        if (
            len(msg) == 2 and
            msg[0] in ['clan'] and
            (msg[1].lower()).startswith('s')
        ):
            clanid = await get_clan.get_clan_data(
                aid=aid,
                server=server
            )
            if (
                clanid['status'] != 'ok' or
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            if clanid['data']['cid'] == None:
                return {'status':'ok','message':'NOT IN CLAN'}
            clanid = clanid['data']['cid']
            cvc_season = (msg[1].lower()).replace('s','')
            try:
                cvc_season = int(cvc_season)
            except:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_clan_season.main,
                'parameter':[
                    clanid,
                    server,
                    lang,
                    cvc_season
                ]
            }
        if (
            len(msg) == 2 and
            msg[0] in ['clan'] and
            msg[1] in ['history']
        ):
            clanid = await get_clan.get_clan_data(
                aid=aid,
                server=server
            )
            if (
                clanid['status'] != 'ok' or
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            if clanid['data']['cid'] == None:
                return {'status':'ok','message':'NOT IN CLAN'}
            clanid = clanid['data']['cid']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_clan_history.main,
                'parameter':[
                    clanid,
                    server,
                    lang
                ]
            }
        if (
            len(msg) == 1 and
            msg[0] in ['clan']
        ):
            clanid = await get_clan.get_clan_data(
                aid=aid,
                server=server
            )
            if (
                clanid['status'] != 'ok' or
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            if clanid['data']['cid'] == None:
                return {'status':'ok','message':'NOT IN CLAN'}
            clanid = clanid['data']['cid']
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_clan_info.main,
                'parameter':[
                    clanid,
                    server,
                    lang
                ]
            }
        return func_not_found_msg
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
