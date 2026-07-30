from ._base import program_error, ship_id_sort
import os
import time
import gc
import json
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
    call_api,
    dog_tag,
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
        path = '/b/sd-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'verson': '13.11',
            'use_ac': parameter[3],
            'ac': parameter[4]
        }
        if parameter[3] is False:
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
            lang=parameter[2],
            pic_num=1
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
    lang: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    res_img = Picture.imread(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_sd.png'))

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
        text_1 = '所属工会:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = '用户令牌:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        if result['data']['token'] == {}:
            box_list.append(
                Box_Data(
                    xy=(
                    (430,445),
                    (630,510)
                    ),
                    fill=(250,130,130)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(169+w_2+40, 448),
                    text='未授权',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
        else:
            box_list.append(
                Box_Data(
                    xy=(
                    (430,445),
                    (630,510)
                    ),
                    fill=(137,216,183)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(169+w_2+40, 448),
                    text='已授权',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
    elif lang == 'en':
        text_1 = 'User\'s Clan:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = 'Token:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
    '''
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag(
                img=res_img,
                aid=aid,
                cid=result['data']['clans'].get('clan_id',None),
                server=server,
                response=result['dog_tag']
            )
    '''
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag(res_img, aid, server, result['dog_tag'])
    fontStyle = fonts.data[1][70]
    w = Picture.x_coord('2024年圣诞补给箱(直营服)', fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 602),
            text='2024年圣诞补给箱(直营服)',
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )
    json_path = os.path.join(plugin_path,'json',f'sd_reward_2024_wg.json')
    with open(json_path, "r", encoding="utf-8") as temp:
        sd_reward = json.load(temp)
    reward_list = {
        'list1':{
            '1':[],
            '2':[]
        },
        'list2':{
            '1':[],
            '2':[]
        },
        'list3':{
            '1':[],
            '2':[]
        }
    }
    ship_port_dict = []
    ship_id_dict = {}
    for ship_data in result['data']['ships']:
        ship_id_dict[ship_data['ship_id']] = ship_data['ship_info']
        if ship_data['in_port'] is True:
            ship_port_dict.append(ship_data['ship_id'])
    for reward_index in ['list1','list2','list3']:
        for ship_id in sd_reward[reward_index]:
            ship_tier = ship_id_dict[ship_id]['ship_tier']
            ship_type = ship_id_dict[ship_id]['ship_type']
            ship_name = ship_id_dict[ship_id]['ship_name']
            if ship_id in ship_port_dict:
                reward_list[reward_index]['1'].append([ship_id,ship_tier,ship_type,ship_name])
            else:
                reward_list[reward_index]['2'].append([ship_id,ship_tier,ship_type,ship_name])
    start_x_dict = {
        'list1':845+140,
        'list2':1874+140,
        'list3':3108+140
    }
    fontStyle = fonts.data[2][80]
    for reward_index in ['list1','list2','list3']:
        owned = f"{len(reward_list[reward_index]['1'])} / {len(sd_reward[reward_index])}"
        w = Picture.x_coord(owned, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2210-w, start_x_dict[reward_index]-145),
                text=owned,
                fill=(152,152,152),
                font_index=2,
                font_size=80
            )
        )
        i = 0
        sort_dict_1 = ship_id_sort(reward_list[reward_index]['1'])
        sort_dict_2 = ship_id_sort(reward_list[reward_index]['2'])
        for ship_info in sort_dict_1:
            x = int(i % 4)
            y = int(i/4)
            ship_name = f"{Game_Data.tier_dict[ship_info[1]]}  {Game_Data.type_dict[ship_info[2]]}  {ship_info[3]}"
            text_list.append(
                Text_Data(
                    xy=(196+540*x+3, start_x_dict[reward_index]+70*y+3),
                    text=ship_name,
                    fill=(128,128,128),
                    font_index=1,
                    font_size=40
                )
            )
            text_list.append(
                Text_Data(
                    xy=(196+540*x, start_x_dict[reward_index]+70*y),
                    text=ship_name,
                    fill=(230,230,128),
                    font_index=1,
                    font_size=40
                )
            )
            i += 1
        for ship_info in sort_dict_2:
            x = int(i % 4)
            y = int(i/4)
            ship_name = f"{Game_Data.tier_dict[ship_info[1]]}  {Game_Data.type_dict[ship_info[2]]}  {ship_info[3]}"
            text_list.append(
                Text_Data(
                    xy=(196+540*x, start_x_dict[reward_index]+70*y),
                    text=ship_name,
                    fill=(101,101,101),
                    font_index=1,
                    font_size=40
                )
            )
            i += 1
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 4440),
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
    return res_img
