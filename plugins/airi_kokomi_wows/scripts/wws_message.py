import os
import json
from .time_zone import value_date
from ..data_source import plugin_path


def main(result: str, lang: str):
    json_path = os.path.join(plugin_path,'lang',f'{lang}.json')
    with open(json_path, "r", encoding="utf-8") as temp:
        data = json.load(temp)
    msg_id = result['message']
    if msg_id == 'DATE NOT FOUND':
        date_num = str(value_date(
            date_num=result['data']['date_count'],
            server=result['data']['server']
        ))
        msg = data.get(msg_id,None).replace('{index}',date_num)
        return msg
    else:
        msg = data.get(msg_id,None)
        if msg == None:
            return f'UndefinedMessage:{msg_id}'
        else:
            return msg