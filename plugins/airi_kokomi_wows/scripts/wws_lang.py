def get_default_lang(
    platform:str,
    platform_id:str,
    channel_id:str
):
    lang = None
    if platform in ['qq_bot','qq_group','qq_guild']:
        lang = 'cn'
    if platform in ['discord']:
        if channel_id == '1236595725459132546':
            lang == 'en'
        elif channel_id == '1236596062957994016':
            lang == 'ja'
        elif channel_id == '1236595725685493780':
            lang == 'cn'
        else:
            lang = 'en'
    return lang