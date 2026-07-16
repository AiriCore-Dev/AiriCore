import os
from PIL import ImageFont
from .path import plugin_path

class Load_Fonts:
    def __init__(self):
        self.fonts_dict = {
            1:[15, 25, 30, 35, 40, 45, 50, 55, 65, 70, 80, 100],
            2:[30, 35, 40, 50, 65, 80, 110]
        }

    def load_fonts(self):
        res = {
            1:{},
            2:{}
        }
        fonts_path_dict = {
            1:os.path.join(plugin_path,'fonts','SHSCN.ttf'),
            2:os.path.join(plugin_path,'fonts','NZBZ.ttf')
        }
        for font_index, font_data in self.fonts_dict.items():
            for font_data_index in font_data:
                res[font_index][font_data_index] = ImageFont.truetype(
                    font=fonts_path_dict[font_index],
                    size=font_data_index,
                    encoding="utf-8"
                )
        return res

class Fonts:
    data = Load_Fonts().load_fonts()

fonts = Fonts