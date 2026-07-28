import base64
import os
import json
import numpy as np
import time
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
from .config import Plugin_Config
from .load_fonts import fonts
from .path import plugin_path
from . import cache

class Authorization:
    def get_authorization() -> str:
        api_token = Authorization.get_token()
        authorization = f'{Plugin_Config.API_TYPE} {api_token}'
        return authorization

    def get_token() -> str:
        return Plugin_Config.API_USERNAME + Plugin_Config.API_PASSWORD

class Text_Data:
    def __init__(
        self,
        xy: tuple,
        text: str,
        fill: tuple,
        font_index: int,
        font_size: int
    ):
        self.xy = xy
        self.text = text
        self.fill = fill
        self.font_index = font_index
        self.font_size = font_size

class Box_Data:
    def __init__(
        self,
        xy: tuple,
        fill: tuple,
    ):
        self.xy = xy
        self.fill = fill

class Game_Data:
    tier_dict = {
        1: 'Ⅰ',
        2: 'Ⅱ',
        3: 'Ⅲ',
        4: 'Ⅳ',
        5: 'Ⅴ',
        6: 'Ⅵ',
        7: 'Ⅶ',
        8: 'Ⅷ',
        9: 'Ⅸ',
        10: 'Ⅹ',
        11: '★',
    }

    type_dict = {
        'AirCarrier': 'CV',
        'Battleship': 'BB',
        'Cruiser': 'CA',
        'Destroyer': 'DD',
        'Submarine': 'SS',
    }

    border_color = {
        "4293348272": "0x282828",
        "4292299696": "0x23325d",
        "4291251120": "0x15668c",
        "4290202544": "0x213f47",
        "4289153968": "0x3a4a23",
        "4288105392": "0x553b16",
        "4287056816": "0x6d4f29",
        "4286008240": "0x8a763a",
        "4284959664": "0xd9d9d9",
        "4283911088": "0xf3c612",
        "4282862512": "0xcb7208",
        "4281813936": "0xa73a1c",
        "4280765360": "0xa32323",
        "4279716784": "0x7f1919",
        "4278668208": "0x382c4f"
    }

    background_color = {
        "4293577648": "0x252525",
        "4292529072": "0x25355d",
        "4291480496": "0x2b6e91",
        "4290431920": "0x22454a",
        "4289383344": "0x3f4d2c",
        "4288334768": "0x8f7e44",
        "4287286192": "0x8b6932",

        "4286237616": "0xc9c9c9",
        "4285189040": "0xcfa40f",
        "4284140464": "0xd98815",
        "4283091888": "0xb74522",
        "4282043312": "0xad1d1d",
        "4280994736": "0x771d27",
        "4279946160": "0x3b2f4e"
    }



    def load_dog_tag_data(server:str):
        if server == 'ru':
            file_path = os.path.join(plugin_path, 'json', 'dog_tags_lesta.json')
        else:
            file_path = os.path.join(plugin_path, 'json', 'dog_tags_wg.json')
        with open(file_path, "r", encoding="utf-8") as file_json:
            json_data = json.load(file_json)
        return json_data

    def load_ship_preview_data(lang:str):
        file_path = os.path.join(plugin_path, 'json', f'ship_preview_{lang}.json')
        with open(file_path, "r", encoding="utf-8") as file_json:
            json_data = json.load(file_json)
        return json_data



class Picture:
    def hex_to_rgb(hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return (r, g, b)

    def return_img(img: Image.Image) -> str:
        func_dict = {
            'base64': Picture.img_to_b64,
            'file': Picture.img_to_file
        }
        func = func_dict[Plugin_Config.RETURN_PIC_TYPE]
        return func(img)

    def img_to_b64(pic: Image.Image) -> str:
        buf = BytesIO()
        pic=pic.convert('RGB')
        pic.save(buf, format="JPEG", quality=95)
        base64_str = base64.b64encode(buf.getbuffer()).decode()
        return "base64://" + base64_str

    def img_to_file(pic: Image.Image) -> str:
        if Plugin_Config.BOT_PLATFORM == 'qq_group':
            file_name = os.path.join('/var/www/html/wws_image', str(time.time()*1000) + '.png')
            pic.save(file_name)
            return file_name
        else:
            file_name = os.path.join(plugin_path, 'temp', str(time.time()*1000) + '.png')
            pic.save(file_name)
            return file_name


    def cv2_to_pil(res_img):
        if (
            isinstance(
                res_img,
                np.ndarray
            )
        ):
            if res_img.ndim == 3 and res_img.shape[2] == 4:
                rgb = res_img[:, :, [2, 1, 0, 3]]
                return Image.fromarray(rgb, mode='RGBA')
            elif res_img.ndim == 3 and res_img.shape[2] == 3:
                rgb = res_img[:, :, ::-1]
                return Image.fromarray(rgb, mode='RGB')
            else:
                return Image.fromarray(res_img)

    def imread(path):
        return cache.get_array(path)

    def resize(img, fx, fy):
        h, w = img.shape[0], img.shape[1]
        new_w = int(round(w * fx))
        new_h = int(round(h * fy))
        if img.ndim == 3 and img.shape[2] == 4:
            pil_img = Image.fromarray(img[:, :, [2, 1, 0, 3]], mode='RGBA')
            resized = pil_img.resize((new_w, new_h), Image.BILINEAR)
            arr = np.array(resized)
            return arr[:, :, [2, 1, 0, 3]].copy()
        elif img.ndim == 3 and img.shape[2] == 3:
            pil_img = Image.fromarray(img[:, :, ::-1], mode='RGB')
            resized = pil_img.resize((new_w, new_h), Image.BILINEAR)
            arr = np.array(resized)
            return arr[:, :, ::-1].copy()
        else:
            pil_img = Image.fromarray(img)
            resized = pil_img.resize((new_w, new_h), Image.BILINEAR)
            return np.array(resized).copy()

    def vconcat(img_list):
        return np.concatenate(img_list, axis=0)


    def x_coord(in_str: str, font: ImageFont.FreeTypeFont) -> float:
        x = font.getlength(in_str)
        return x

    def formate_str(in_str: str, str_len, max_len):
        if str_len <= max_len:
            return in_str
        else:
            return in_str[:int(max_len/str_len*len(in_str))-2] + '...'

    def add_box(box_list, res_img):
        if box_list is None:
            return res_img
        img = ImageDraw.ImageDraw(res_img)
        for index in box_list:
            index: Box_Data
            img.rectangle(
                xy=index.xy,
                fill=index.fill,
                outline=None
            )
        return res_img

    def add_text(text_list, res_img):
        if text_list is None:
            return res_img
        draw = ImageDraw.Draw(res_img)
        for index in text_list:
            index: Text_Data
            fontStyle = fonts.data[index.font_index][index.font_size]
            draw.text(
                xy=index.xy,
                text=index.text,
                fill=index.fill,
                font=fontStyle
            )
        return res_img

    def add_alpha_channel(img):
        alpha_channel = np.ones(
            (img.shape[0], img.shape[1]), dtype=img.dtype) * 255
        img_new = np.dstack((img[:, :, 0], img[:, :, 1], img[:, :, 2], alpha_channel))
        return img_new


    def merge_img(jpg_img, png_img, y1, y2, x1, x2):
        if jpg_img.shape[2] == 3:
            jpg_img = Picture.add_alpha_channel(jpg_img)
        if png_img.shape[2] == 3:
            png_img = Picture.add_alpha_channel(png_img)
        yy1 = 0
        yy2 = png_img.shape[0]
        xx1 = 0
        xx2 = png_img.shape[1]
        if x1 < 0:
            xx1 = -x1
            x1 = 0
        if y1 < 0:
            yy1 = - y1
            y1 = 0
        if x2 > jpg_img.shape[1]:
            xx2 = png_img.shape[1] - (x2 - jpg_img.shape[1])
            x2 = jpg_img.shape[1]
        if y2 > jpg_img.shape[0]:
            yy2 = png_img.shape[0] - (y2 - jpg_img.shape[0])
            y2 = jpg_img.shape[0]
        alpha_png = png_img[yy1:yy2, xx1:xx2, 3] / 255.0
        alpha_jpg = 1 - alpha_png
        for c in range(0, 3):
            jpg_img[y1:y2, x1:x2, c] = (
                (alpha_jpg*jpg_img[y1:y2, x1:x2, c]) + (alpha_png*png_img[yy1:yy2, xx1:xx2, c])
            )
        return jpg_img

class Message:
    server_dict = {
        'asia': 'asia',
        'aisa': 'asia',
        'as': 'asia',
        '亚服': 'asia',
        'na': 'na',
        '美服': 'na',
        '北美': 'na',
        'ru': 'ru',
        '俄服': 'ru',
        '莱服': 'ru',
        'eu': 'eu',
        '欧服': 'eu',
        'cn': 'cn',
        '国服': 'cn'
    }