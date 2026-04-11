from ..kokomi_chs import *

async def main(
    extra: None
):
    varm=["help_list", "me_list", "rank_list", "cw_list", "info_list", "season_list", "ship_list", "recent_list", "ships_list", "clan_list", "set_list", "roll_list", "all_list", "pr_list", "server_list", "search_list", "game_list", "bind_list", "group_list", "box_list", "recents_list", "list_list", "naming_list",'lang_list','history_list','status_list','oper_list','online_list','sd_list','sx_list']
    name_str="KokomiBot - Momoi Airi定制版\n目前定义的参数别称:\n\n触发指令: "
    for i in trigger_list:
        name_str+=i.replace(' ','')
        name_str+=', '
    name_str=name_str[:-2]
    name_str+='\n\n快捷指令：'
    for i in trigger_shortcut_list:
        name_str+=i.replace(' ','')
        name_str+=', '
    name_str=name_str[:-2]
    name_str+='\n\n'
    for x in varm:
        y=eval(x)
        name_str+=y[0]
        name_str+=': '
        for i in y[1:]:
            name_str+=i
            name_str+=', '
        name_str=name_str[:-2]
        name_str+='\n\n'
    name_str = name_str[:-2]
    return {'status': 'info', 'message': name_str}
