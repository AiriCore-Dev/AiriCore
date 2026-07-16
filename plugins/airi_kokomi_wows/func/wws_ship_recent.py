from ._base import program_error
import os
import time
import gc
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
    call_api,
    dog_tag,
    time_zone,
    fonts,
    plugin_path
)

async def main(
    parameter: list,
) -> dict:
    result = await get_data(
        parameter=parameter
    )
    return result

async def get_data(
    parameter: list,
) -> dict:
    try:
        path = '/r1/ship-recent-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'ship_id':parameter[3],
            'start_date':parameter[4],
            'end_date': parameter[5],
            'use_pr':parameter[6],
            'use_ac': parameter[7],
            'ac': parameter[8]
        }
        if parameter[7] is False:
            del params['use_ac']
            del params['ac']
        res = await call_api.call_api(
            params=params,
            path=path
        )
        if (
            res['status'] != 'ok' or
            res['message'] != 'SUCCESS'
        ):
            return res
        res_img = get_png(
            result=res,
            aid=parameter[0],
            server=parameter[1],
            lang=parameter[2]
        )
        result = {
            'status': 'ok',
            'message': 'SUCCESS',
            'img': None
        }
        result['img'] = Picture.return_img(img=res_img)
        del res_img
        return result
    except Exception as e:
        return program_error(e, __file__, parameter)
    finally:
        gc.collect()


def get_png(
    result: dict,
    aid: str,
    server: str,
    lang: str
) -> str:
    text_list = []
    box_list = []
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_shiprecent.png'))
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img = Picture.imread(os.path.join(plugin_path, 'png', 'list', '80_50.png'))
    for i in range(list_png_len):
        res_img = Picture.vconcat([res_img, list_img])
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=result['nickname'],
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    text_list.append(
        Text_Data(
            xy=(199, 275),
            text=f'{server.upper()} -- {aid}',
            fill=(80, 80, 80),
            font_index=1,
            font_size=45
        )
    )
    fontStyle = fonts.data[1][55]
    if result['data']['clans']['clan_tag'] != 'None':
        tag = '['+str(result['data']['clans']['clan_tag'])+']'
    else:
        tag = str(result['data']['clans']['clan_tag'])
    tag_color = Picture.hex_to_rgb(result['data']['clans']['clan_color'])
    if lang == 'cn':
        text_list.append(
            Text_Data(
                xy=(466, 355),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        creat_time = time.strftime(
            "%Y-%m-%d",
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(466, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_list.append(
            Text_Data(
                xy=(555, 355),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        creat_time = time.strftime(
            "%Y-%m-%d",
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(525, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    ship_name = result['data']['ship_info']['ship_name']
    ship_tier = result['data']['ship_info']['ship_tier']
    ship_index = result['data']['ship_info']['ship_index']
    ship_nation = result['data']['ship_info']['ship_nation']
    ship_type = result['data']['ship_info']['ship_type']
    premium = result['data']['ship_info']['premium']
    special = result['data']['ship_info']['special']

    ship_name_str = Game_Data.tier_dict[ship_tier] + '    ' + ship_name
    nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_index}.png')
    if os.path.exists(nation_png_path) is False:
        nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_nation}.png')
    if premium:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Premium.png')
    elif special:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Special.png')
    else:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Elite.png')

    fontStyle = fonts.data[1][70]
    w = Picture.x_coord(ship_name_str, fontStyle)
    all_len = 180+140+w
    text_list.append(
        Text_Data(
            xy=(all_len/2+1214-w, 602),
            text=ship_name_str,
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )

    nation_png = Picture.imread(nation_png_path)
    nation_png = Picture.resize(nation_png, 2, 2)
    x1 = int(1214-all_len/2)
    y1 = 580
    x2 = x1 + nation_png.shape[1]
    y2 = y1 + nation_png.shape[0]
    res_img = Picture.merge_img(res_img, nation_png, y1, y2, x1, x2)
    type_png = Picture.imread(type_png_path)
    x1 = int(1214-all_len/2+180)
    y1 = 593
    x2 = x1 + type_png.shape[1]
    y2 = y1 + type_png.shape[0]
    res_img = Picture.merge_img(res_img, type_png, y1, y2, x1, x2)
    pr_png = result['data']['pr']['avg_pr_index']
    pr_png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'pr', '{}.png'.format(pr_png))
    pr_png = Picture.imread(pr_png_path)
    x1 = 132
    y1 = 757
    x2 = x1 + pr_png.shape[1]
    y2 = y1 + pr_png.shape[0]
    res_img = Picture.merge_img(res_img, pr_png, y1, y2, x1, x2)
    del pr_png
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag(res_img, aid, server, result['dog_tag'])
    text_list.append(
        Text_Data(
            xy=(132+result['data']['pr']['avg_pr_text'], 820),
            text=result['data']['pr']['avg_pr_des'],
            fill=(255, 255, 255),
            font_index=1,
            font_size=35
        )
    )
    str_pr = '{:,}'.format(result['data']['pr']['avg_pr'])
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(str_pr, fontStyle)
    text_list.append(
        Text_Data(
            xy=(2284-w, 772),
            text=str_pr,
            fill=(255, 255, 255),
            font_index=1,
            font_size=80
        )
    )
    index = result['data']['pr']['battle_type'].upper()
    x0 = 324
    y0 = 990
    temp_data = result['data']['pr']
    battles_count = temp_data['battles_count']
    avg_win = temp_data['win_rate']
    avg_damage = temp_data['avg_damage']
    avg_frag = temp_data['avg_frags']
    avg_xp = temp_data['avg_exp']
    win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
    avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
    avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])

    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(battles_count, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*0-w/2, y0),
            text=battles_count,
            fill=(0, 0, 0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_win, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*1-w/2, y0),
            text=avg_win,
            fill=win_rate_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_damage, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*2-w/2, y0),
            text=avg_damage,
            fill=avg_damage_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_frag, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*3-w/2, y0),
            text=avg_frag,
            fill=avg_frags_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_xp, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*4-w/2, y0),
            text=avg_xp,
            fill=(0, 0, 0),
            font_index=1,
            font_size=80
        )
    )
    fontStyle = fonts.data[1][45]
    start_time = time_zone.get_str_time(result['data']['time']['start_time'],result['data']['time']['time_zone'])
    end_time = time_zone.get_str_time(result['data']['time']['end_time'],result['data']['time']['time_zone'])
    timezone = f"(UTC+{str(result['data']['time']['time_zone'])})" if result['data']['time']['time_zone'] >= 0 else f"(UTC{str(result['data']['time']['time_zone'])})"
    if lang == 'cn':
        time_str = f'数据统计区间:  {start_time} ~ {end_time}  {timezone}'
    elif lang == 'en':
        time_str = f'Time interval:  {start_time} ~ {end_time}  {timezone}'
    w = Picture.x_coord(time_str, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 1165),
            text=time_str,
            fill=(100,100,100),
            font_index=1,
            font_size=45
        )
    )
    i = 0
    fontStyle = fonts.data[1][55]
    for index in ['pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo']:
        x0 = 0
        y0 = 1469
        temp_data = result['data']['battle_type'][index]
        battles_count = temp_data['battles_count']
        avg_win = temp_data['win_rate']
        avg_damage = temp_data['avg_damage']
        avg_frag = temp_data['avg_frags']
        avg_xp = temp_data['avg_exp']
        win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
        avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
        avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])
        avg_pr_color = Picture.hex_to_rgb(temp_data['avg_pr_color'])
        if temp_data['avg_pr_des'] == '-':
            str_pr = '-'
        else:
            if lang == 'cn':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
            elif lang == 'en':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(588-w/2+x0, y0+90*i),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(955-w/2+x0, y0+90*i),
                text=str_pr,
                fill=avg_pr_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1307-w/2+x0, y0+90*i),
                text=avg_win,
                fill=win_rate_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1613-w/2+x0, y0+90*i),
                text=avg_damage,
                fill=avg_damage_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1909-w/2+x0, y0+90*i),
                text=avg_frag,
                fill=avg_frags_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2177-w/2+x0, y0+90*i),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
    i = 0
    x0 = 0
    y0 = 2061
    for date_data in result['data']['date']:
        box_list.append(
            Box_Data(
                xy=(
                    (97,y0-10+90*i),
                    (485,y0-20+90*(i+1))
                ),
                fill=(223,224,226)
            )
        )
        battle_date = date_data['battle_date'][:4]+'-'+date_data['battle_date'][4:6]+'-'+date_data['battle_date'][6:]
        text_list.append(
            Text_Data(
                xy=(145, y0+90*i),
                text=battle_date,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
        for index in ['pvp_solo', 'pvp_div2', 'pvp_div3', 'rank_solo']:
            fontStyle = fonts.data[1][55]
            temp_data = date_data[index]
            if temp_data == {}:
                continue
            battles_count = temp_data['battles_count']
            avg_win = temp_data['win_rate']
            avg_damage = temp_data['avg_damage']
            avg_frag = temp_data['avg_frags']
            avg_xp = temp_data['avg_exp']
            survival_rate = temp_data['survival_rate']
            hit_ratio = temp_data['hit_ratio']
            win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
            avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
            avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])
            avg_pr_color = Picture.hex_to_rgb(temp_data['avg_pr_color'])
            if temp_data['avg_pr_des'] == '-':
                str_pr = '-'
            else:
                if lang == 'cn':
                    str_pr = '■ '+str(int(temp_data['avg_pr']))
                elif lang == 'en':
                    str_pr = '■ '+str(int(temp_data['avg_pr']))
            if lang == 'cn':
                battle_type_dict = {
                    'pvp_solo':'单野',
                    'pvp_div2':'双排',
                    'pvp_div3':'三排',
                    'rank_solo':'排位'
                }
            elif lang == 'en':
                battle_type_dict = {
                    'pvp_solo':'PVP SOLO',
                    'pvp_div2':'PVP DIV2',
                    'pvp_div3':'PVP DIV3',
                    'rank_solo':'RANK SOLO'
                }
            fontStyle = fonts.data[1][50]
            w = Picture.x_coord(battle_type_dict[index], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(287-w/2+x0, y0+90*i+4),
                    text=battle_type_dict[index],
                    fill=(130,130,130),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(battles_count, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(550-w/2+x0, y0+90*i+4),
                    text=battles_count,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(str_pr, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(834-w/2+x0, y0+90*i+4),
                    text=str_pr,
                    fill=avg_pr_color,
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(avg_win, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1160-w/2+x0, y0+90*i+4),
                    text=avg_win,
                    fill=win_rate_color,
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(avg_damage, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1395-w/2+x0, y0+90*i+4),
                    text=avg_damage,
                    fill=avg_damage_color,
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(avg_frag, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1595-w/2+x0, y0+90*i+4),
                    text=avg_frag,
                    fill=avg_frags_color,
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(avg_xp, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1769-w/2+x0, y0+90*i+4),
                    text=avg_xp,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(survival_rate, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(1978-w/2+x0, y0+90*i+4),
                    text=survival_rate,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
            w = Picture.x_coord(hit_ratio, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(2208-w/2+x0, y0+90*i+4),
                    text=hit_ratio,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
            i += 1
    png_len = 2051 + 90*i + 180
    box_list.append(
        Box_Data(
            xy=(
                (0,png_len-180),
                (2428,png_len-10)
            ),
            fill=(248,249,251)
        )
    )
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, png_len-140),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=80
        )
    )
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 2428, png_len))
    return res_img





