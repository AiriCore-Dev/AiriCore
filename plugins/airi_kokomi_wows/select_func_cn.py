from .data_source import Message
from .log.error_log import write_error
from .kokomi_chs import *
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
    wws_recents,
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
    wws_data,
    wws_names,
    wws_stats,
    wws_roll,
    wws_sd,
    wws_sx
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
    parameter = []
    try:
        params_error_msg = {'status':'ok','message':'PARAMS ERROR'}
        func_not_found_msg = {'status':'ok','message':'FUNC NOT FOUND'}
        # wws help
        if (
            msg[0] in help_list and
            len(msg) == 1
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_help.main,
                'parameter':[
                    lang
                ]
            }
        # wws names
        if (
            msg[0] in naming_list and
            len(msg) == 1
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_names.main,
                'parameter':[
                    lang
                ]
            }
        # wws bind server xxx
        if (
            msg[0] in set_list and
            len(msg) >= 3
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
                    user_id if len(msg)==3 else msg[3],
                    aid,
                    server,
                    use_pr,
                    lang
                ]
            }
        # wws server set xxx
        if (
            len(msg) >= 3 and
            msg[1] in set_list
        ):
            server = Message.server_dict.get(msg[0],None)
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
                    user_id if len(msg)==3 else msg[3],
                    aid,
                    server,
                    use_pr,
                    lang
                ]
            }
        if aid == None:
            return {'status':'ok','message':'NO BIND DATA'}
        # wws me
        if (
            msg[0] in me_list and
            len(msg) == 1
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
            Message.server_dict.get(msg[0],None) != None and
            len(msg) == 2
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
        # wws me bind
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in bind_list
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
        # wws pr
        if (
            len(msg) == 2 and
            msg[0] in pr_list and
            msg[1] in ['on','off','开','关']
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_pr.main,
                'parameter':[
                    platform,
                    user_id,
                    lang,
                    True if msg[1] in ['on','开'] else False
                ]
            }
        # wws lang
        if (
            len(msg) == 2 and
            msg[0] in lang_list and
            msg[1] in ['cn','en','中','英','中文','英文','英语']
        ):
            if msg[1] in ['cn','中','中文']:
                msg[1] = 'cn'
            elif msg[1] in ['en','英','英文','英语']:
                msg[1] = 'en'
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_lang.main,
                'parameter':[
                    platform,
                    user_id,
                    msg[1]
                ]
            }
        # wws recent\recents on
        if (
            len(msg) == 2 and
            (msg[0] in recent_list or msg[0] in recents_list) and
            msg[1] in ['on','off','开','关']
        ):
            if msg[1] in ['off','关']:
                return {'status':'ok','message':'PLEASE CONNECT AUTHOR'}
            if msg[0] in recent_list:
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
            elif msg[0] in recents_list:
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
        # wws me rank
        if (
            msg[0] in me_list and
            msg[1] in rank_list and
            len(msg) == 2
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in rank_list and
            len(msg) == 3
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
        # wws me rank season
        if (
            len(msg) == 3 and
            msg[0] in me_list and
            msg[1] in rank_list and
            (msg[2].lower()).startswith('s')
        ):
            rank_season = (msg[2].lower()).replace('s','')
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
            len(msg) == 4 and
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in rank_list and
            (msg[3].lower()).startswith('s') and
            msg[1] not in ship_list
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            rank_season = (msg[3].lower()).replace('s','')
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
        # wws me sx
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in sx_list
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_sx.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac,
                    1
                ]
            }
        if (
            len(msg) == 3 and
            Message.server_dict.get(msg[0].lower(),None) != None and
            msg[2] in sx_list
        ):
            server = Message.server_dict.get(msg[0].lower(),None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_sx.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac,
                    1
                ]
            }
        # wws me info
        if (
            msg[0] in me_list and
            msg[1] in ['info'] and
            len(msg) == 2
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_info.main,
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in ['info'] and
            len(msg) == 3
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_info.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        # wws me oper 
        if (
            msg[0] in me_list and
            msg[1] in oper_list and
            len(msg) == 2
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in oper_list and
            len(msg) == 3
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_oper.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        # wws me cw
        if (
            msg[0] in me_list and
            msg[1] in cw_list and
            len(msg) == 2
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in cw_list and
            len(msg) == 3
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_cw.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        # wws me ship
        if (
            msg[0] in me_list and
            msg[1] in ship_list and
            msg[-2] not in recent_list+rank_list and
            msg[-1] not in recent_list and
            len(msg) >= 3
        ):
            if len(msg) == 3:
                ship_name = msg[2]
            else:
                name_tmp = ''
                for i in msg[2:]:
                    if i in recent_list: break
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in ship_list and
            len(msg) == 4
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            ship_name = msg[3]
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
        # wws me sd
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in sd_list
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_sd.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) == 3 and
            Message.server_dict.get(msg[0].lower(),None) != None and
            msg[2] in sd_list
        ):
            server = Message.server_dict.get(msg[0].lower(),None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_sd.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_ac,
                    ac
                ]
            }
        # wws search
        if (
            len(msg) >= 2 and
            msg[0] in search_list
        ):
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[1:]
            )
            if filter_data is None:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_name.main,
                'parameter':[
                    lang,
                    filter_data[2],
                    filter_data[3],
                    filter_data[4]
                ]
            }
        # wws roll
        if (
            len(msg) >= 1 and
            msg[0] in roll_list
        ):
            if len(msg) == 1:
                filter_data = filter_criteria.main(
                    lang=lang,
                    params=['dd','ca','cv','ss','bb']
                )
            else:
                filter_data = filter_criteria.main(
                    lang=lang,
                    params=msg[1:]
                )
            if filter_data is None:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_roll.main,
                'parameter':[
                    lang,
                    filter_data[2],
                    filter_data[3],
                    filter_data[4]
                ]
            }
        # wws stats ship
        if (
            len(msg) == 3 and
            msg[0] in status_list and
            msg[1] in ship_list
        ):
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
                'function':wws_stats.main,
                'parameter':[
                    lang,
                    shipid
                ]
            }
        # wws status 
        if (
            len(msg) >= 2 and
            msg[0] in status_list
        ):
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[1:]
            )
            if filter_data is None:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_data.main,
                'parameter':[
                    server,
                    lang,
                    filter_data[2],
                    filter_data[3],
                    filter_data[4]
                ]
            }
        if (
            len(msg) >= 3 and
            Message.server_dict.get(msg[0],None) != None and
            msg[1] in status_list
        ):
            server = Message.server_dict.get(msg[0],None)
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[2:]
            )
            if filter_data is None:
                return params_error_msg
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_data.main,
                'parameter':[
                    server,
                    lang,
                    filter_data[2],
                    filter_data[3],
                    filter_data[4]
                ]
            }
        # wws me ships
        if (
            msg[0] in me_list and
            msg[1] in ships_list and
            len(msg) >= 3
        ):
            if len(msg) == 3 and msg[2] in all_list:
                msg = ['me','ships','ss','dd','ca','bb','cv']
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[2:]
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
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in ships_list and
            len(msg) >= 4
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            if len(msg) == 4 and msg[3] in all_list:
                msg = ['me','1','ships','ss','dd','ca','bb','cv']
            filter_data = filter_criteria.main(
                lang=lang,
                params=msg[3:]
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
        # wws me recent
        if (
            len(msg) <= 3 and
            msg[0] in me_list and
            msg[1] in recent_list
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
                    'pvp',
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) <= 4 and
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in recent_list
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
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
            len(msg) <= 4 and
            msg[0] in me_list and
            msg[1] in rank_list and
            msg[2] in recent_list
        ):
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
                'function':wws_recent.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    'rank',
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        if (
            len(msg) <= 5 and
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in rank_list and
            msg[3] in recent_list
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            if len(msg) == 4:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[4]) == 17 and msg[4][8] in ['~','-']:
                    date_1 = msg[4][:8]
                    date_2 = msg[4][9:]
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
                        date_num = int(msg[4])
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
                    'rank',
                    time_data[0],
                    time_data[1],
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        # wws me ship recent
        if (
            msg[0] in me_list and
            msg[1] in ship_list and
            (msg[-2] in recent_list or msg[-1] in recent_list)
        ):
            if len(msg) <= 5:
                ship_name = msg[2]
            else:
                name_tmp = ''
                for i in msg[2:]:
                    if i in recent_list: break
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
            if msg[-1] in recent_list:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[-1]) == 17 and msg[-1][8] in ['~','-']:
                    date_1 = msg[-1][:8]
                    date_2 = msg[-1][9:]
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
                        date_num = int(msg[-1])
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
            len(msg) <= 6 and
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in ship_list and
            msg[4] in recent_list
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            ship_name = msg[3]
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
            if len(msg) == 5:
                date_num = 1
                time_data = time_zone.get_str_server_time(
                    server=server,
                    date_num=date_num
                )
            else:
                if len(msg[5]) == 17 and msg[5][8] in ['~','-']:
                    date_1 = msg[5][:8]
                    date_2 = msg[5][9:]
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
                        date_num = int(msg[5])
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
        # wws me ship rank
        if (
            len(msg) == 4 and
            msg[0] in me_list and
            msg[1] in ship_list and
            msg[2] in rank_list
        ):
            ship_name = msg[3]
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
            len(msg) == 5 and
            Message.server_dict.get(msg[0],None) != None and
            msg[2] in ship_list and
            msg[3] in rank_list
        ):
            server = Message.server_dict.get(msg[0],None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
            )
            if (
                nickname['status'] != 'ok' or 
                nickname['message'] != 'SUCCESS'
            ):
                return nickname
            aid = nickname['data'][0]['aid']
            ship_name = msg[4]
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
        # wws server ship rank
        if (
            len(msg) == 4 and
            Message.server_dict.get(msg[0],None) != None and
            msg[1] in ship_list and
            msg[2] in rank_list
        ):
            server = Message.server_dict.get(msg[0],None)
            if server is None:
                return params_error_msg
            ship_name = msg[3]
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
        # wws online
        if (
            msg[0] in online_list
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_online.main,
                'parameter':[
                    lang
                ]
            }
        # wws me clan season
        if (
            len(msg) == 3 and
            msg[0] in me_list and
            msg[1] in clan_list and
            (msg[2].lower()).startswith('s')
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
            cvc_season = (msg[2].lower()).replace('s','')
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
            len(msg) == 4 and
            Message.server_dict.get(msg[0],None) != None and
            (msg[1] in clan_list or msg[2] in clan_list) and
            (msg[3].lower()).startswith('s')
        ):
            server = Message.server_dict.get(msg[0],None)
            if server is None:
                return params_error_msg
            if msg[1] in clan_list:
                clan_name = msg[2]
            else:
                clan_name = msg[1]
            clanid = await search_clan.search_clan(
                server=server,
                clan_tag=clan_name
            )
            if (
                clanid['status'] != 'ok' or 
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            clanid = clanid['data'][0]['clan_id']
            cvc_season = (msg[3].lower()).replace('s','')
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
        # wws me clan history
        if (
            len(msg) == 3 and
            msg[0] in me_list and
            msg[1] in clan_list and
            msg[2] in history_list
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
            len(msg) == 4 and
            Message.server_dict.get(msg[0],None) != None and
            (msg[1] in clan_list or msg[2] in clan_list) and
            msg[3] in history_list
        ):
            server = Message.server_dict.get(msg[0],None)
            if server is None:
                return params_error_msg
            if msg[1] in clan_list:
                clan_name = msg[2]
            else:
                clan_name = msg[1]
            clanid = await search_clan.search_clan(
                server=server,
                clan_tag=clan_name
            )
            if (
                clanid['status'] != 'ok' or 
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            clanid = clanid['data'][0]['clan_id']
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
        # wws me clan
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in clan_list
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
        if (
            len(msg) == 3 and
            Message.server_dict.get(msg[0],None) != None and
            (msg[1] in clan_list or msg[2] in clan_list)
        ):
            server = Message.server_dict.get(msg[0],None)
            if server is None:
                return params_error_msg
            if msg[1] in clan_list:
                clan_name = msg[2]
            else:
                clan_name = msg[1]
            clanid = await search_clan.search_clan(
                server=server,
                clan_tag=clan_name
            )
            if (
                clanid['status'] != 'ok' or 
                clanid['message'] != 'SUCCESS'
            ):
                return clanid
            try:
                clanid = clanid['data'][0]['clan_id']
            except:
                return {'status':'ok','message':'CLAN NOT EXIST'}
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
        # wws me recents
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in recents_list
        ):
            return {
                'status':'ok',
                'message':'SUCCESS',
                'function':wws_recents.main,
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
            len(msg) == 3 and
            Message.server_dict.get(msg[0].lower(),None) != None and
            msg[2] in ['recents']
        ):
            server = Message.server_dict.get(msg[0].lower(),None)
            nickname = await search_user.search_user(
                server=server,
                nickname=msg[1]
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
                'function':wws_recents.main,
                'parameter':[
                    aid,
                    server,
                    lang,
                    use_pr,
                    use_ac,
                    ac
                ]
            }
        # wws me 周/月/年报
        if (
            len(msg) == 2 and
            msg[0] in me_list and
            msg[1] in ['周报','月报','年报','weekly','2024']
        ):
            return {'status':'ok','message':'TEMP_1'}
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
