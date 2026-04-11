import time
from datetime import datetime
from ..config import Plugin_Config

server_time_zone = {
    'asia':8,
    'eu':1,
    'na':-7,
    'ru':5,
    'cn':8
}

def get_str_server_time(server: str, date_num: int):
    now_time = int(time.time())
    server_index = server_time_zone[server]
    server_time =  now_time - 60*60*(Plugin_Config.LOCAL_TIME_ZONE-server_index)
    hour = time.strftime("%H", time.localtime(server_time))
    if hour in [0,1,2,3]:
        date_num += 1
    start_time = server_time
    end_time = server_time - 24*60*60*date_num
    end_time_str = time.strftime("%Y%m%d", time.localtime(start_time))
    start_time_str = time.strftime("%Y%m%d", time.localtime(end_time))
    return (
        start_time_str,
        end_time_str
    )

def value_date(date_num:int,server:str):
    date_num -= 1
    now_time = int(time.time())
    server_index = server_time_zone[server]
    server_time =  now_time - 60*60*(Plugin_Config.LOCAL_TIME_ZONE-server_index)
    hour = time.strftime("%H", time.localtime(server_time))
    if hour in [0,1,2,3]:
        date_num -= 1
    return date_num

def get_str_time(timetemp:int, utc:int):
    server_time =  timetemp - 60*60*(Plugin_Config.LOCAL_TIME_ZONE-utc)
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(server_time))
    return time_str

def date_to_timestamp(date_str):
    try:
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        timestamp = datetime.timestamp(date_obj)
        return int(timestamp)
    except ValueError:
        return None