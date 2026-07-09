"""本地静态图片 / 字体的进程内缓存(内存换 CPU/IO)。

签到、收藏各命令每次都要 ``Image.open`` 一批固定不变的 UI 素材(mask/overlay/头像框/
进度条蒙版/集章底图)和 ``ImageFont.truetype`` 同一批字体。文件不变,重复解码纯浪费。
这里做一层进程内缓存:

- ``get_image(path)``  返回**共享只读**的 RGBA Image。只能当 paste 源、``.split()`` 取
  mask、``alpha_composite`` 源用,**禁止 mutate**(不要对它 ``ImageDraw.Draw`` / ``paste``
  写入)。``resize``/``crop`` 返回新对象,不动母图,安全。
- ``get_image_copy(path)``  返回一份新副本,给需要 draw / 被 paste 写入的底图用。
- ``get_font(path, size)``  缓存 ``ImageFont``(只读)。

图片缓存带 LRU 上限:本插件 sticker 图很多且分主题、单张又大,故**只该缓存固定 UI 素材
和少量主题 bg/mask**,上限主要用来兜底防多主题把内存撑爆(作者对内存敏感)。
"""

import threading
from collections import OrderedDict

from PIL import Image, ImageFont

# 母图缓存上限:固定 UI 素材十几张 + 几套主题的 bg/mask,64 足够且能兜底。
_MAX_IMAGES = 64

_lock = threading.Lock()
_images: "OrderedDict[str, Image.Image]" = OrderedDict()  # path -> 共享只读 RGBA
_fonts = {}  # (path, size) -> ImageFont


def get_image(path: str) -> Image.Image:
    """返回共享只读的 RGBA Image(禁止 mutate)。需要写入的底图请用 get_image_copy。"""
    with _lock:
        img = _images.get(path)
        if img is not None:
            _images.move_to_end(path)
            return img
    # 解码放到锁外,避免持锁做重活;并发重复解码同一路径也无害(后写覆盖)
    img = Image.open(path).convert("RGBA")
    with _lock:
        _images[path] = img
        _images.move_to_end(path)
        while len(_images) > _MAX_IMAGES:
            _images.popitem(last=False)
    return img


def get_image_copy(path: str) -> Image.Image:
    """返回一份可写副本,给需要 ImageDraw / 被 paste 写入的底图用。"""
    return get_image(path).copy()


def get_font(path: str, size: int):
    """返回缓存的 ImageFont(只读,可跨命令共享)。"""
    key = (path, size)
    with _lock:
        f = _fonts.get(key)
    if f is not None:
        return f
    f = ImageFont.truetype(font=path, size=size)
    with _lock:
        _fonts[key] = f
    return f
