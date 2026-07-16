import os
from ..data_source import (
    Picture,
    Text_Data,
    plugin_path,
    fonts
)

def clan_tag(
    img,
    text_list: list,
    response: dict,
    x1: int = 1912,
    y1: int = 131
):
    if response == {}:
        return img
    if response['stage'] == {}:
        cvc_png_path = os.path.join(plugin_path, 'png', 'clan', '{}-{}-normal.png'.format(
            response['league'],
            response['division'])
        )
        cvc_png = Picture.imread(cvc_png_path)
        cvc_png = Picture.resize(cvc_png, 0.824, 0.824)
        x2 = x1 + cvc_png.shape[1]
        y2 = y1 + cvc_png.shape[0]
        img = Picture.merge_img(img, cvc_png, y1, y2, x1, x2)
        division_rating = str(response['division_rating'])
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord(division_rating, fontStyle)
        text_list.append(
            Text_Data(
                xy=(x1+210-w/2, y1+344),
                text=division_rating,
                fill=(230, 230, 230),
                font_index=1,
                font_size=55
            )
        )
        return img, text_list
    else:
        cvc_png_path = os.path.join(plugin_path, 'png', 'clan', '{}-{}-{}.png'.format(
            response['league'],
            response['division'],
            response['stage']['type']
            )
        )
        cvc_png = Picture.imread(cvc_png_path)
        cvc_png = Picture.resize(cvc_png, 0.824, 0.824)
        x2 = x1 + cvc_png.shape[1]
        y2 = y1 + cvc_png.shape[0]
        img = Picture.merge_img(img, cvc_png, y1, y2, x1, x2)
        victory_png_path = os.path.join(plugin_path, 'png', 'clan', 'victory.png')
        defeat_png_path = os.path.join(plugin_path, 'png', 'clan', 'defeat.png')
        victory_png = Picture.imread(victory_png_path)
        victory_png = Picture.resize(victory_png, 0.824, 0.824)
        defeat_png = Picture.imread(defeat_png_path)
        defeat_png = Picture.resize(defeat_png, 0.824, 0.824)
        i = 0
        for index in response['stage']['progress']:
            if index == 'victory':
                x2 = int(x1 + 76.6 + 56.85*i)
                y2 = y1 + 351
                x3 = x2 + victory_png.shape[1]
                y3 = y2 + victory_png.shape[0]
                img = Picture.merge_img(img, victory_png, y2, y3, x2, x3)
            else:
                x2 = int(x1 + 76.6 + 56.85*i)
                y2 = y1 + 351
                x3 = x2 + defeat_png.shape[1]
                y3 = y2 + defeat_png.shape[0]
                img = Picture.merge_img(img, defeat_png, y2, y3, x2, x3)
            i += 1
        del victory_png
        del defeat_png
        return img, text_list