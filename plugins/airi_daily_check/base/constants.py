import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join('data', 'airi_daily_check')
DATA_FILE = os.path.join(DATA_DIR, 'data.pk')

hidden_stickers = [17, 13, 37, 20, 100]

TRANSFER_DAILY_MAX = 200

DIFFICULTY = [0, 'NORMAL', 'EXPERT', 'MASTER']
CREDIT_BY_DIFF = [0, 20, 100, 300]

SECRET_MESSAGES = [
    '💬 嘀嘀嘀……我们好像收到一条秘密的摩斯密码！\n-.-..----.-...- -..-...........- -........---.. ---..-...--...- -.....---...-..- ------.--.--..- --...-....-...- -..-.--.-..-.... -....-.---..---- --..-.-..--.--. -....-.---..---- -.-.-..--.....- -........---.- -.---....--...- -.......------.- --...-.-------- -.-..-...--.... .---- --... -.-..------.--- --------.......-',
    '💬 剧烈的大风刮过来一张纸条，这是base64吗？\n6YeN5aSN562+5Yiw5LiA5qyh5Y2z5Y+v6I635b6XMTPlj7fmlLbol4/lk4HvvIzkupTmrKHojrflvpczN+WPt+aUtuiXj+WTge+8gQ==',
    '💬 你正在路上走着，突然跑过来一个瑞典人跟你说：\nMed två tusen poäng kan du låsa upp den hemliga samlingen nummer tjugo!',
    '💬 隐藏Tip: 连续签到7天即可获得100号收藏品！……',
]

NOT_REGISTERED_TIP = '❌ 账号未注册！\n请先签到一次！\n发送"签到"即可'


def asset(*parts):
    return os.path.join(BASE_DIR, *parts)


def new_account():
    return {
        'credits': 0,
        'checked_days': 0,
        'collections': [],
        'check_times_daily': 0,
        'receive_transfer_daily': 0,
        'reborn_times': 0,
        "need_reborn": 0,
        "theme": "airi_momo",
        "daily_challenge": [0, 0, 0, 0],
        'jrys': 0,
        'last_check_time': 0,
    }
