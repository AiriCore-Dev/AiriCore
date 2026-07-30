import re
from .scripts import (
    get_bind,
    default_lang,
    wws_error,
    wws_message
)
from .config import Plugin_Config
from .data_source import SafeMessage
from .select_func_cn import main as main_cn
from .select_func_en import main as main_en
from .kokomi_chs import *

class select_funtion:
    async def main(
        msg:list,
        user_id:str,
        user_data:dict,
        platform:str,
        platform_id:str,
        channel_id:str,
        platform_data:dict
    ):
        msg = SafeMessage(msg)
        tot = 0
        while 1:
            if len(msg) > 1:
                if (
                    msg[1].startswith('[cq:at,qq=') and
                    msg[1].endswith(']')
                ) or (
                    msg[1].startswith('<@!') and
                    msg[1].endswith('>')
                ):
                    user_id = (re.findall(r'\d+', msg[1]))[0]
                    msg[1] = 'me'

            bind_data = await get_bind.get_bind_data(
                platform=platform,
                uid=user_id
            )
            if (
                bind_data['status'] == 'ok' and
                bind_data['message'] == 'NO BIND DATA'
            ):
                lang = default_lang.get_default_lang(
                    platform=platform,
                    platform_id=platform_id,
                    channel_id=channel_id
                )
                aid=None
                server=None
                use_pr=True
                use_ac=False
                ac=None
            elif (
                bind_data['status'] != 'ok' or
                bind_data['message'] != 'SUCCESS'
            ):
                lang = default_lang.get_default_lang(
                    platform=platform,
                    platform_id=platform_id,
                    channel_id=channel_id
                ) or 'cn'
                return select_funtion.return_data(
                    result=bind_data,
                    lang=lang
                )
            else:
                aid=bind_data['data']['aid']
                server=bind_data['data']['server']
                use_pr=bind_data['data']['use_pr']
                lang=bind_data['data']['lang']
                use_ac=False
                ac=None

            if '你自己' in msg:
                aid='2051054400'
                server='asia'
                use_pr=True
                lang='cn'
                use_ac=False
                ac=None

            if lang not in ['cn', 'en']:
                lang = default_lang.get_default_lang(
                    platform=platform,
                    platform_id=platform_id,
                    channel_id=channel_id
                ) or 'cn'
            '''
            if lang == 'cn':
                if msg[0] == Plugin_Config.CN_START_WITH:
                    del msg[0]
            if lang == 'en':
                if Plugin_Config.EN_START_WITH == msg[0]:
                    del msg[0]
                if Plugin_Config.EN_START_WITH == msg[0][0]:
                    msg[0] = msg[0].replace(Plugin_Config.EN_START_WITH,'')
                if msg[0] == Plugin_Config.CN_START_WITH:
                    del msg[0]
                if msg[0] in me_list and len(msg)>1:
                    del msg[0]
            '''
            if msg[0][:4] == "[cq:":
                del msg[0]
            if msg[0] == Plugin_Config.CN_START_WITH:
                del msg[0]
            if lang == 'en' and msg[0] in me_list and len(msg)>1:
                del msg[0]

            if lang == 'cn':
                select_result = await main_cn(
                    msg=msg,
                    user_id=user_id,
                    user_data=user_data,
                    platform=platform,
                    platform_id=platform_id,
                    channel_id=channel_id,
                    platform_data=platform_data,

                    aid=aid,
                    server=server,
                    use_pr=use_pr,
                    lang=lang,
                    use_ac=use_ac,
                    ac=ac
                )
            elif lang == 'en':
                select_result = await main_en(
                    msg=msg,
                    user_id=user_id,
                    user_data=user_data,
                    platform=platform,
                    platform_id=platform_id,
                    channel_id=channel_id,
                    platform_data=platform_data,

                    aid=aid,
                    server=server,
                    use_pr=use_pr,
                    lang=lang,
                    use_ac=use_ac,
                    ac=ac
                )
            if select_result['status'] == 'ok' and select_result['message'] == 'SUCCESS':
                function = select_result['function']
                result = await function(select_result['parameter'])
            else:
                result = select_result
            if result['message'] in ['NETWORK FAILURE','NETWORK TIMEOUT'] and tot < 3:
                tot += 1
                continue
            else:
                return select_funtion.return_data(
                    result=result,
                    lang=lang
                )

    def return_data(
        result:dict,
        lang:str
    ):
        if result['status'] == 'ok' and result['message'] == 'SUCCESS':
            return {
                'type': 'img',
                'msg': None,
                'img': result['img']
            }
        elif result['status'] == 'ok' and result['message'] != 'SUCCESS':
            return_msg = wws_message.main(result=result,lang=lang)
            return {
                'type': 'msg',
                'msg': return_msg,
                'img': None
            }
        elif result['status'] == 'info':
            return {
                'type': 'msg',
                'msg': result['message'],
                'img': None
            }
        else:
            return_img = wws_error.main(result=result,lang=lang)
            return {
                'type': 'img',
                'msg': None,
                'img': return_img['img']
            }
