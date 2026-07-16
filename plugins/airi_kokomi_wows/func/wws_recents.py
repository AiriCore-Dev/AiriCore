from ._base import program_error
import os
import time
from PIL import Image
from utils import asset_cache
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
        path = '/r2/recents-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'use_pr':parameter[3],
            'use_ac': parameter[4],
            'ac': parameter[5]
        }
        if parameter[4] is False:
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
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_recents.png'))
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
    battle_type = result['data']['pr']['battle_type']
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
    elif lang == 'ja':
        text_list.append(
            Text_Data(
                xy=(390, 355),
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
                xy=(390, 445),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    battle_type = result['data']['pr']['battle_type']
    pr_png = result['data']['pr']['avg_pr_index']
    pr_png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'pr', '{}.png'.format(pr_png))
    pr_png = Picture.imread(pr_png_path)
    x1 = 132
    y1 = 627
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
            xy=(132+result['data']['pr']['avg_pr_text'], 690),
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
            xy=(2284-w, 642),
            text=str_pr,
            fill=(255, 255, 255),
            font_index=1,
            font_size=80
        )
    )
    index = result['data']['pr']['battle_type'].upper()
    x0 = 324
    y0 = 860
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
    elif lang == 'ja':
        time_str = f'統計区間です:  {start_time} ~ {end_time}  {timezone}'
    w = Picture.x_coord(time_str, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 1035),
            text=time_str,
            fill=(100,100,100),
            font_index=1,
            font_size=45
        )
    )
    i = 0
    fontStyle = fonts.data[1][55]
    battle_type_list = ['pvp_solo', 'pvp_div2', 'pvp_div3','rank_solo']
    for index in battle_type_list:
        x0 = 0
        y0 = 1339
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
            elif lang == 'ja':
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
    res_img = Picture.cv2_to_pil(
        res_img=res_img
    ).convert('RGBA')
    i = 0
    x0 = 0
    y0 = 1930
    ship_preview_data = Game_Data.load_ship_preview_data(lang)
    ship_preview_jpg_path = os.path.join(plugin_path,'png',f'bg_{lang}',f'ship_preview_{lang}.png')
    ship_preview_jpg = asset_cache.get_image(ship_preview_jpg_path)
    for ship_data in result['data']['recents']:
        fontStyle = fonts.data[1][50]
        ship_index = ship_data['ship_info']['ship_index']
        battle_time = ship_data['battle_time']
        battle_time_diff = ship_data['battle_time_diff']
        battle_type = ship_data['battle_type']
        battle_type_color = ship_data['battle_type_color']
        ship_preview_num = ship_preview_data.get(ship_index,None)
        if ship_preview_num != None:
            x = (ship_preview_num % 10)
            y = int(ship_preview_num / 10)
            ship_png = ship_preview_jpg.crop(
                ((0+360*x), (0+80*y), (360+360*x), (80+80*y)))
            res_img.paste(ship_png, (97, y0-10+90*i), mask = ship_png.split()[3])
        else:
            w = Picture.x_coord(ship_data['ship_info']['ship_name'][:6], fontStyle)
            text_list.append(
                Text_Data(
                    xy=(285-w/2+x0, y0+90*i+4),
                    text=ship_data['ship_info']['ship_name'][:6],
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
        batte_result_color = Picture.hex_to_rgb(ship_data['battle_result'])
        box_list.append(
            Box_Data(
                xy=(
                    ((457, y0-10+90*i)),
                    ((2331, y0-10+90*i+80))
                ),
                fill=batte_result_color
            )
        )
        temp_data = ship_data['ship_data']
        if temp_data == {}:
            continue
        battles_count = temp_data['battles_count']
        avg_win = temp_data['win_rate']
        avg_damage = temp_data['avg_damage']
        avg_frag = temp_data['avg_frags']
        avg_xp = temp_data['avg_exp']
        avg_planes = temp_data['avg_planes_killed']
        avg_art_agro = temp_data['avg_art_agro']
        avg_scouting_damage = temp_data['avg_scouting_damage']
        avg_xp = temp_data['avg_exp']
        hit_ratio = temp_data['hit_ratio']
        win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
        avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
        avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])
        avg_pr_color = Picture.hex_to_rgb(temp_data['avg_pr_color'])
        if temp_data['avg_pr_des'] == '-':
            str_pr = '-'
        else:
            str_pr = '■ '+str(int(temp_data['avg_pr']))
        w = Picture.x_coord(battle_time, fontStyle)
        text_list.append(
            Text_Data(
                xy=(560-w/2+x0, y0+90*i+4),
                text=battle_time,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        if battle_time_diff == -1:
            text_list.append(
                Text_Data(
                    xy=(635+x0, y0+90*i+4),
                    text='-1',
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=25
                )
            )
        w = Picture.x_coord(battle_type, fontStyle)
        text_list.append(
            Text_Data(
                xy=(728-w/2+x0, y0+90*i+4),
                text=battle_type,
                fill=battle_type_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(904-w/2+x0, y0+90*i+4),
                text=str_pr,
                fill=avg_pr_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1121-w/2+x0, y0+90*i+4),
                text=avg_damage,
                fill=avg_damage_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1306-w/2+x0, y0+90*i+4),
                text=avg_frag,
                fill=avg_frags_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_planes, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1462-w/2+x0, y0+90*i+4),
                text=avg_planes,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1623-w/2+x0, y0+90*i+4),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(hit_ratio, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1806-w/2+x0, y0+90*i+4),
                text=hit_ratio,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_art_agro, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2020-w/2+x0, y0+90*i+4),
                text=avg_art_agro,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_scouting_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w/2+x0, y0+90*i+4),
                text=avg_scouting_damage,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        i += 1
    del ship_preview_jpg
    png_len = 1920 + 90*i + 180
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
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 2428, png_len))
    return res_img






