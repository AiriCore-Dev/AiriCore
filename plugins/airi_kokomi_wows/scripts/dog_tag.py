import os
import cv2
import random
from nonebot import logger
from ..data_source import (
    Plugin_Config,
    Picture,
    Game_Data,
    plugin_path
)



dir_list = [
    'PCNA001', 
    'PCNA002', 
    'PCNA003', 
    'PCNA004', 
    'PCNA005', 
    'PCNA006', 
    'PCNA007', 
    'PCNA008', 
    'PCNA009'
]
def dog_tag(
    img,
    aid: str,
    server: str,
    response: dict,
    x1: int = 1912,
    y1: int = 132
):
    dog_tag_data = Game_Data.load_dog_tag_data(server=server)
    background_id = dog_tag_data.get(str(response['background_id']), None)
    symbol_id = dog_tag_data.get(str(response['symbol_id']), None)
    if (
        (
            background_id == None and 
            symbol_id == None
        ) or (
            background_id != None and 
            symbol_id == None
        )
    ):
        return img
    custom_png_path = os.path.join(plugin_path, 'png', 'dog_tag_custom', f'{aid}')
    special_png_path = os.path.join(plugin_path, 'png', 'dog_tag_special', f'{aid}')
    try:
        assert(os.path.isdir(custom_png_path))
    except:
        custom_png_path += '.png'
    else:
        custom_png_path = os.path.join(custom_png_path, random.choice(os.listdir(custom_png_path)))
    try:
        assert(os.path.isdir(special_png_path))
    except:
        special_png_path += '.png'
    else:
        special_png_path = os.path.join(special_png_path, random.choice(os.listdir(special_png_path)))
    if server == 'ru':
        server = 'lesta'
    else:
        server = 'wg'
    if  Plugin_Config.SHOW_SPECIAL_TAG is True and os.path.exists(special_png_path):
        symbol = cv2.imread(special_png_path, cv2.IMREAD_UNCHANGED)
        x1 = 98
        x2 = 129
        x2 = x1 + symbol.shape[1]
        y2 = y1 + symbol.shape[0]
        img = Picture.merge_img(img, symbol, y1, y2, x1, x2)
        del symbol
    elif Plugin_Config.SHOW_CUSTOM_TAG is True and os.path.exists(custom_png_path):
        symbol = cv2.imread(custom_png_path, cv2.IMREAD_UNCHANGED)
        symbol = cv2.resize(symbol, None, fx=0.818, fy=0.818)
        x2 = x1 + symbol.shape[1]
        y2 = y1 + symbol.shape[0]
        img = Picture.merge_img(img, symbol, y1, y2, x1, x2)
        del symbol
    elif background_id in dir_list:
        if symbol_id == None:
            return img
        texture_id = dog_tag_data[str(response['texture_id'])][6:]
        background_color_id = Game_Data.background_color[str(response['background_color_id'])]
        background_png_path = os.path.join(plugin_path , 'png', 'dog_tag_2', f'{background_id}_background_{texture_id}_{background_color_id}.png')
        background = cv2.imread(background_png_path, cv2.IMREAD_UNCHANGED)
        background = cv2.resize(background, None, fx=0.818, fy=0.818)
        x2 = x1 + background.shape[1]
        y2 = y1 + background.shape[0]
        img = Picture.merge_img(img, background, y1, y2, x1, x2)
        del background
        border_color_id = Game_Data.border_color[str(
            response['border_color_id'])]
        border_png_path = os.path.join(plugin_path , 'png', 'dog_tag_2', f'{background_id}_border_{border_color_id}.png')
        border = cv2.imread(border_png_path, cv2.IMREAD_UNCHANGED)
        border = cv2.resize(border, None, fx=0.818, fy=0.818)
        x2 = x1 + border.shape[1]
        y2 = y1 + border.shape[0]
        img = Picture.merge_img(img, border, y1, y2, x1, x2)
        del border
        symbol_png_path = os.path.join(plugin_path , 'png', f'dog_tag_{server}', f'{symbol_id}.png')
        symbol = cv2.imread(symbol_png_path, cv2.IMREAD_UNCHANGED)
        symbol = cv2.resize(symbol, None, fx=0.818, fy=0.818)
        x2 = x1 + symbol.shape[1]
        y2 = y1 + symbol.shape[0]
        img = Picture.merge_img(img, symbol, y1, y2, x1, x2)
        del symbol
    elif background_id == None and symbol_id != None:
        symbol_png_path = os.path.join(plugin_path , 'png', f'dog_tag_{server}', f'{symbol_id}.png')
        symbol = cv2.imread(symbol_png_path, cv2.IMREAD_UNCHANGED)
        symbol = cv2.resize(symbol, None, fx=0.818, fy=0.818)
        x2 = x1 + symbol.shape[1]
        y2 = y1 + symbol.shape[0]
        img = Picture.merge_img(img, symbol, y1, y2, x1, x2)
        del symbol
    else:
        background_png_path = os.path.join(plugin_path , 'png', f'dog_tag_{server}', f'{background_id}.png')
        background = cv2.imread(background_png_path, cv2.IMREAD_UNCHANGED)
        background = cv2.resize(background, None, fx=0.818, fy=0.818)
        x2 = x1 + background.shape[1]
        y2 = y1 + background.shape[0]
        img = Picture.merge_img(img, background, y1, y2, x1, x2)
        del background
        symbol_png_path = os.path.join(plugin_path , 'png', f'dog_tag_{server}', f'{symbol_id}.png')
        symbol = cv2.imread(symbol_png_path, cv2.IMREAD_UNCHANGED)
        symbol = cv2.resize(symbol, None, fx=0.818, fy=0.818)
        x2 = x1 + symbol.shape[1]
        y2 = y1 + symbol.shape[0]
        img = Picture.merge_img(img, symbol, y1, y2, x1, x2)
        del symbol
    return img
