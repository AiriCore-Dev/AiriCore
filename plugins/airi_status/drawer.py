import platform
import os
import random
import numpy as np
from io import BytesIO
from pathlib import Path

import cpuinfo
import nonebot
#from nonebot import get_plugin_config
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from nonebot.config import Config as BotConfig
from nonebot import __version__ as __nb_version__
from nonebot import get_driver

from .model import get_status_info
from .utils import truncate_string
#from . import __version__ as __status_version__
from .path import (
    adlam_font_path,
    baotu_font_path,
    marker_img_path,
    spicy_font_path,
)
from .color import (
    cpu_color,
    ram_color,
    disk_color,
    swap_color,
    details_color,
    nickname_color,
    transparent_color,
)

#bot_config = get_plugin_config(BotConfig)
driver = get_driver()
airicore_version = getattr(driver.config, "airicore_version", "")

system = platform.uname()

# 真实服务器信息（cpuinfo 较慢，模块加载时取一次即可）
_real_cpu_model = cpuinfo.get_cpu_info().get("brand_raw", "") or platform.processor() or "Unknown CPU"
_real_os_info = f"{system.system} {system.release} {system.machine}"


def _resolve(config_key: str, real_value: str) -> str:
    """配置项非空则用配置值替换，为空则回退到真实信息"""
    value = getattr(driver.config, config_key, "")
    value = str(value).strip() if value is not None else ""
    return value if value else real_value

adlam_fnt = ImageFont.truetype(str(adlam_font_path), 36)
spicy_fnt = ImageFont.truetype(str(spicy_font_path), 38)
baotu_fnt = ImageFont.truetype(str(baotu_font_path), 64)
_nick_size = 75
# 中文昵称用支持 CJK 的 baotu.ttf，非中文继续用 baotu_fnt(ADLaMDisplay)
_baotu_cjk_font_path = Path(__file__).parent / "resources" / "fonts" / "baotu.ttf"
baotu_cjk_fnt = ImageFont.truetype(str(_baotu_cjk_font_path), _nick_size)


def _has_cjk(text: str) -> bool:
    """判断字符串是否包含中文（CJK 统一表意文字）"""
    return any("一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" for ch in text)


# ---------------------------------------------------------------------------
# 跨平台字体回退（font fallback）
#
# PIL 不会自动回退：字库里没有的字形（如 ✶ U+2736）会渲染成豆腐块。
# 这里逐字符检测覆盖，缺失的字符用系统里带该字形的字体单独渲染，
# 其余字符仍用原字体，互不影响。生产在 Linux，故候选路径覆盖多系统。
# ---------------------------------------------------------------------------

# 系统符号/CJK 回退字体候选（按优先级；只挑存在的加载）。
# 可用 .env 的 status_fallback_fonts 追加自定义路径（逗号分隔，优先级最高）。
_FALLBACK_FONT_CANDIDATES = [
    # Linux 常见
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/google-noto/NotoSansSymbols2-Regular.ttf",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    # macOS 常见
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/System/Library/Fonts/ZapfDingbats.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    # Windows 常见
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/arialuni.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_fallback_fonts(size: int) -> list[ImageFont.FreeTypeFont]:
    """加载存在的回退字体（配置项路径优先）。"""
    fonts: list[ImageFont.FreeTypeFont] = []
    custom = getattr(driver.config, "status_fallback_fonts", "") or ""
    custom_paths = [p.strip() for p in str(custom).split(",") if p.strip()]
    for path in custom_paths + _FALLBACK_FONT_CANDIDATES:
        try:
            if os.path.exists(path):
                fonts.append(ImageFont.truetype(path, size))
        except Exception:
            continue
    return fonts


# 昵称尺寸下的回退字体，模块加载时构建一次
_fallback_fnts = _load_fallback_fonts(_nick_size)

# 每个字体的 .notdef（豆腐块）签名缓存，用于判断字形是否缺失
_notdef_cache: dict[int, bytes | None] = {}
# (font id, char) -> 是否有真实字形
_glyph_cache: dict[tuple[int, str], bool] = {}


def _render_char_bytes(font: ImageFont.FreeTypeFont, ch: str) -> bytes | None:
    """把单字符渲染到位图并返回像素字节，失败返回 None。"""
    try:
        mask = font.getmask(ch, mode="L")
        if mask is None:
            return None
        return Image.frombytes("L", mask.size, bytes(mask)).tobytes()
    except Exception:
        return None


def _notdef_signature(font: ImageFont.FreeTypeFont) -> bytes | None:
    """取该字体 .notdef 字形的像素签名（用一个几乎不可能有字形的码位）。"""
    fid = id(font)
    if fid not in _notdef_cache:
        _notdef_cache[fid] = _render_char_bytes(font, "￿")
    return _notdef_cache[fid]


def _has_glyph(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    """字体是否真的有该字符的字形（区别于渲染成豆腐块）。"""
    key = (id(font), ch)
    if key in _glyph_cache:
        return _glyph_cache[key]
    if ch in (" ", "\t"):
        _glyph_cache[key] = True
        return True
    rendered = _render_char_bytes(font, ch)
    if rendered is None:
        result = False
    else:
        notdef = _notdef_signature(font)
        # 与 .notdef 位图相同 → 无字形；空白位图也视为无字形
        result = rendered != notdef and any(rendered)
    _glyph_cache[key] = result
    return result


def _font_for_char(base_font: ImageFont.FreeTypeFont, ch: str) -> ImageFont.FreeTypeFont:
    """优先用 base_font，缺字形则在回退字体里找第一个能渲染的。"""
    if _has_glyph(base_font, ch):
        return base_font
    for fnt in _fallback_fnts:
        if _has_glyph(fnt, ch):
            return fnt
    return base_font  # 都没有，退回 base（渲染成豆腐块，至少不崩）


def _draw_text_fallback(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    base_font: ImageFont.FreeTypeFont,
    fill,
) -> float:
    """逐字符渲染，缺字形的字符用回退字体单独画。返回文本总宽度。"""
    x, y = xy
    start_x = x
    for ch in text:
        fnt = _font_for_char(base_font, ch)
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += fnt.getlength(ch)
    return x - start_x

class LiquidGlass:
    def __init__(
        self,
        displacement_scale: float = 70,
        blur_amount: float = 12,
        saturation: float = 140,
        aberration_intensity: float = 2,
        corner_radius: int = 999,
        edge_highlight_intensity: float = 0.3,
        white_overlay_opacity: float = 0.25,
    ):
        self.displacement_scale = displacement_scale
        self.blur_amount = blur_amount
        self.saturation = saturation
        self.aberration_intensity = aberration_intensity
        self.corner_radius = corner_radius
        self.edge_highlight_intensity = edge_highlight_intensity
        self.white_overlay_opacity = white_overlay_opacity

    def _create_rounded_mask(self, size: tuple[int, int]) -> Image.Image:
        scale_factor = 4
        w, h = size
        large_size = (w * scale_factor, h * scale_factor)
        
        mask = Image.new("L", large_size, 0)
        draw = ImageDraw.Draw(mask)
        large_radius = self.corner_radius * scale_factor
        draw.rounded_rectangle([(0, 0), large_size], radius=large_radius, fill=255)
        
        mask = mask.resize(size, Image.Resampling.LANCZOS)
        return mask

    def _create_edge_highlight(self, size: tuple[int, int]) -> Image.Image:
        w, h = size
        highlight = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(highlight)
        
        line_width_outer = 3
        line_width_inner = 1
        alpha_outer = int(255 * self.edge_highlight_intensity * 0.8)
        alpha_inner = int(255 * self.edge_highlight_intensity * 1.2)
        
        alpha_outer = min(255, max(0, alpha_outer))
        alpha_inner = min(255, max(0, alpha_inner))

        highlight_radius_outer = max(self.corner_radius - 1, 0)
        outer_rect = [(0, 0), (w, h)] 
        temp_outer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_outer)
        temp_draw.rounded_rectangle(
            outer_rect, 
            radius=highlight_radius_outer, 
            outline=(255, 255, 255, alpha_outer), 
            width=line_width_outer
        )
        temp_outer = temp_outer.filter(ImageFilter.GaussianBlur(radius=1))
        
        highlight_radius_inner = max(self.corner_radius - 1, 0)
        inner_rect = [(1, 1), (w - 1, h - 1)]
        temp_inner = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        temp_draw_inner = ImageDraw.Draw(temp_inner)
        temp_draw_inner.rounded_rectangle(
            inner_rect, 
            radius=highlight_radius_inner, 
            outline=(255, 255, 255, alpha_inner), 
            width=line_width_inner
        )

        highlight = Image.alpha_composite(highlight, temp_outer)
        highlight = Image.alpha_composite(highlight, temp_inner)
        return highlight

    def _adjust_saturation(self, img: Image.Image, saturation: float) -> Image.Image:
        img_array = np.array(img.convert("RGB"))
        hsv = Image.fromarray(img_array).convert("HSV")
        h, s, v = hsv.split()
        s = Image.fromarray(np.clip(np.array(s) * (saturation / 100), 0, 255).astype(np.uint8))
        return Image.merge("HSV", (h, s, v)).convert("RGB")

    def _chromatic_aberration(self, img: Image.Image, intensity: float) -> Image.Image:
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
        offset = int(intensity)
        r_shifted = np.roll(r, offset, axis=1)
        b_shifted = np.roll(b, -offset, axis=1)
        aberration = np.dstack([r_shifted, g, b_shifted])
        return Image.fromarray(aberration.astype(np.uint8))

    def _generate_displacement_map(self, size: tuple[int, int]) -> Image.Image:
        w, h = size
        x = np.linspace(0, 1, w)
        y = np.linspace(0, 1, h)
        xx, yy = np.meshgrid(x, y)
        center_x, center_y = 0.5, 0.5
        dist = np.sqrt((xx - center_x)**2 + (yy - center_y)**2)
        displacement = np.clip(1 - dist * 2, 0, 1)
        disp_r = (displacement * 255).astype(np.uint8)
        disp_g = (displacement * 255).astype(np.uint8)
        disp_b = disp_g
        disp_map = np.dstack([disp_r, disp_g, disp_b])
        return Image.fromarray(disp_map)

    def _apply_displacement(self, img: Image.Image, disp_map: Image.Image, scale: float) -> Image.Image:
        img_array = np.array(img)
        disp_array = np.array(disp_map)
        h, w = img_array.shape[:2]
        x = np.arange(w)
        y = np.arange(h)
        xx, yy = np.meshgrid(x, y)
        dx = (disp_array[:, :, 0] / 255 - 0.5) * scale
        dy = (disp_array[:, :, 1] / 255 - 0.5) * scale
        new_xx = np.clip(xx + dx, 0, w - 1).astype(int)
        new_yy = np.clip(yy + dy, 0, h - 1).astype(int)
        displaced = img_array[new_yy, new_xx]
        return Image.fromarray(displaced.astype(np.uint8))

    def apply(
        self,
        background_img: Image.Image,
        glass_position: tuple[int, int],
        glass_size: tuple[int, int],
    ) -> Image.Image:
        x, y = glass_position
        w, h = glass_size
        glass_region = background_img.crop((x, y, x + w, y + h)).copy()
        
        rounded_mask = self._create_rounded_mask((w, h))
        
        blurred = glass_region.filter(ImageFilter.GaussianBlur(radius=self.blur_amount))
        saturated = self._adjust_saturation(blurred, self.saturation)
        disp_map = self._generate_displacement_map((w, h))
        displaced = self._apply_displacement(saturated, disp_map, self.displacement_scale)
        aberrated = self._chromatic_aberration(displaced, self.aberration_intensity)

        aberrated_rgba = aberrated.convert("RGBA")
        white_overlay = Image.new(
            "RGBA", 
            (w, h), 
            (0, 0, 0, int(self.white_overlay_opacity * 255))
        )
        glass_with_white = Image.alpha_composite(aberrated_rgba, white_overlay)
        
        glass_with_white.putalpha(rounded_mask)
        
        edge_highlight = self._create_edge_highlight((w, h))
        glass_final = Image.alpha_composite(glass_with_white, edge_highlight)
        
        result = background_img.convert("RGBA")
        result.paste(glass_final, (x, y), glass_final)
        
        return result.convert("RGB")

def draw(nickname: str = "Momoi Airi") -> bytes:
    """绘图"""

    # 配置项非空则替换昵称，为空则使用传入的 bot QQ 昵称
    nickname = _resolve("status_nickname", nickname or "Momoi Airi")

    loaded_plugins = nonebot.get_loaded_plugins()
    
    resources_dir: Path = Path(__file__).parent / "resources"
    bg_img_path: Path = resources_dir / "images" / "background_new"
    bg_img_path: Path = resources_dir / "images" / "background_new" / random.choice(os.listdir(bg_img_path))
    mask_img_path: Path = resources_dir / "images" / "airi_status_mask.png"

    with Image.open(bg_img_path).convert("RGBA") as base:
        mask_img = Image.open(mask_img_path).convert("RGBA")
        img = Image.new("RGBA", base.size, (255, 255, 255, 0))
        marker = Image.open(marker_img_path)
        
        base = Image.alpha_composite(base, Image.new("RGBA", base.size, (0, 0, 0, 40)))
        liquid_glass = LiquidGlass(
            displacement_scale=50,
            blur_amount=16,
            saturation=160,
            aberration_intensity=2,
            corner_radius=50,
            edge_highlight_intensity=0.2,
            white_overlay_opacity=0.35,
        )
        base = liquid_glass.apply(base, glass_position=(100, 575), glass_size=(888, 750))
        base = liquid_glass.apply(base, glass_position=(100, 1358), glass_size=(888, 250))
        base = liquid_glass.apply(base, glass_position=(100, 1639), glass_size=(888, 129))
        base = base.convert("RGBA")

        cpu, ram, swap, disk = get_status_info()

        cpu_cores = _resolve("status_cpu_cores", str(cpu.core))
        cpu_info = f"{cpu.usage}% - {cpu.freq}Ghz [{cpu_cores} cores]"
        ram_info = f"{ram.usage} / {ram.total} GB"
        swap_info = f"{swap.usage} / {swap.total} GB"
        disk_info = f"{disk.usage} / {disk.total} GB"

        # -------------------------------------------------------------------------
        # 【核心修改区域】超采样抗锯齿 (SSAA) 绘制圆弧和椭圆
        # -------------------------------------------------------------------------
        ssaa_scale = 4  # 超采样倍率，2倍通常足够，追求极致可设为4
        img_w, img_h = img.size
        
        # 1. 创建 2x 分辨率的临时画布
        temp_img = Image.new("RGBA", (img_w * ssaa_scale, img_h * ssaa_scale), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_img)

        # 辅助函数：将坐标和尺寸放大
        def s(val):
            return val * ssaa_scale

        # 2. 在高分辨率画布上绘制圆弧 (Arcs)
        # CPU Arc
        temp_draw.arc(
            (s(152), s(724), s(272), s(838)),
            start=-90,
            end=(cpu.usage * 3.6 - 90),
            width=s(115),
            fill=cpu_color,
        )
        # RAM Arc
        temp_draw.arc(
            (s(152), s(878), s(272), s(992)),
            start=-90,
            end=(ram.usage / ram.total * 360 - 90),
            width=s(115),
            fill=ram_color,
        )
        # SWAP Arc
        if swap.total > 0:
            temp_draw.arc(
                (s(152), s(1032), s(272), s(1146)),
                start=-90,
                end=(swap.usage / swap.total * 360 - 90),
                width=s(115),
                fill=swap_color,
            )
        # DISK Arc
        temp_draw.arc(
            (s(152), s(1186), s(272), s(1300)),
            start=-90,
            end=(disk.usage / disk.total * 360 - 90),
            width=s(115),
            fill=disk_color,
        )

        # 3. 在高分辨率画布上绘制椭圆 (Ellipses / 镂空效果)
        temp_draw.ellipse((s(163), s(729), s(261), s(833)), width=s(105), fill=transparent_color)
        temp_draw.ellipse((s(163), s(883), s(261), s(987)), width=s(105), fill=transparent_color)
        temp_draw.ellipse((s(163), s(1037), s(261), s(1141)), width=s(105), fill=transparent_color)
        temp_draw.ellipse((s(163), s(1192), s(261), s(1295)), width=s(105), fill=transparent_color)

        # 4. 使用 LANCZOS 算法缩小回原图尺寸 (这是让线条变丝滑的关键)
        temp_img_resized = temp_img.resize((img_w, img_h), Image.Resampling.LANCZOS)

        # 5. 将抗锯齿后的图形合并回主画布
        img = Image.alpha_composite(img, temp_img_resized)
        
        content = ImageDraw.Draw(img)
        nick_fnt = baotu_cjk_fnt if _has_cjk(nickname) else baotu_fnt
        nick_y = 595 + (5 if _has_cjk(nickname) else 0)
        # 逐字符渲染：base 字体缺字形的字符（如 ✶）自动用系统回退字体
        nickname_length = _draw_text_fallback(
            content, (155, nick_y), nickname, nick_fnt, nickname_color
        )
        content.text((303, 772), cpu_info, font=spicy_fnt, fill=cpu_color)
        content.text((303, 927), ram_info, font=spicy_fnt, fill=ram_color)
        content.text((303, 1081), swap_info, font=spicy_fnt, fill=swap_color)
        content.text((303, 1235), disk_info, font=spicy_fnt, fill=disk_color)

        cpu_model = _resolve("status_cpu_model", _real_cpu_model)
        os_info = _resolve("status_os_info", _real_os_info)

        content.text(
            (352, 1378),
            cpu_model,
            font=adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1431),
            os_info,
            font=adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1484),
            f"{airicore_version}",
            font=adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1537),
            f"{len(loaded_plugins)} loaded",
            font=adlam_fnt,
            fill=details_color,
        )

        img.paste(marker, (155 + int(nickname_length) + 60, 605), marker)

        base = Image.alpha_composite(base, mask_img)
        out = Image.alpha_composite(base, img)
        byte_io = BytesIO()
        out.save(byte_io, format="png")
        img_bytes = byte_io.getvalue()

        return img_bytes





