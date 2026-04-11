import os
import time
import hashlib
from ..path import plugin_path
file_path = os.path.join(plugin_path,'log')

def calculate_md5(data) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(data)
    md5_hexdigest = md5_hash.hexdigest()
    return md5_hexdigest


def write_error(
    error_file: str,
    error_params: list,
    error_name: str,
    error_info: str
) -> str:
    form_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    track_id = calculate_md5(form_time.encode()).upper()
    now_day = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    with open(os.path.join(file_path, f'{now_day}.txt'), "a", encoding="utf-8") as f:
        f.write('-------------------------------------------------------------------------------------------------------------\n')
        f.write(f">Track ID:     {track_id}\n")
        f.write(f">Error Name:   {error_name}\n")
        f.write(f">Error File:   {error_file}\n")
        f.write(f">Error Params: {error_params}\n")
        f.write(f">Error Info: \n")
        f.write(f"{error_info}\n")
        f.write('-------------------------------------------------------------------------------------------------------------\n')
    f.close()
    return track_id