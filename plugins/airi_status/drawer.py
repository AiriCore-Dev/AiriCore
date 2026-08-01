import platform
import os
import random
import numpy as np
from io import BytesIO
from pathlib import Path

import cpuinfo
import nonebot
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from nonebot.config import Config as BotConfig
from nonebot import __version__ as __nb_version__
from nonebot import get_driver

from utils.asset_cache import get_image
from .model import get_status_info
from .utils import truncate_string
from .path import (
    adlam_font_path,
    baotu_cjk_font_path,
    baotu_font_path,
    bg_img_dir,
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
)

driver = get_driver()
airicore_version = getattr(driver.config, "airicore_version", "")

system = platform.uname()

_real_cpu_model = cpuinfo.get_cpu_info().get("brand_raw", "") or platform.processor() or "Unknown CPU"
_real_os_info = f"{system.system} {system.release} {system.machine}"


def _resolve(config_key: str, real_value: str) -> str:
    value = getattr(driver.config, config_key, "")
    value = str(value).strip() if value is not None else ""
    return value if value else real_value

adlam_fnt = ImageFont.truetype(str(adlam_font_path), 36)
spicy_fnt = ImageFont.truetype(str(spicy_font_path), 38)
baotu_fnt = ImageFont.truetype(str(baotu_font_path), 64)
_nick_size = 75
baotu_cjk_fnt = ImageFont.truetype(str(baotu_cjk_font_path), _nick_size)


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" for ch in text)



_FALLBACK_FONT_CANDIDATES = [
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
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/System/Library/Fonts/ZapfDingbats.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/arialuni.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_fallback_fonts(size: int) -> list[ImageFont.FreeTypeFont]:
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


_fallback_fnts = _load_fallback_fonts(_nick_size)

_MAX_GLYPH_CACHE = 20000
_notdef_cache: dict[tuple, bytes | None] = {}
_glyph_cache: dict[tuple, bool] = {}


def _font_key(font: ImageFont.FreeTypeFont) -> tuple:
    try:
        return (str(getattr(font, "path", "")), int(getattr(font, "size", 0) or 0),
                int(getattr(font, "index", 0) or 0))
    except Exception:
        return (repr(font),)


def _render_char_bytes(font: ImageFont.FreeTypeFont, ch: str) -> bytes | None:
    try:
        mask = font.getmask(ch, mode="L")
        if mask is None:
            return None
        return Image.frombytes("L", mask.size, bytes(mask)).tobytes()
    except Exception:
        return None


def _notdef_signature(font: ImageFont.FreeTypeFont) -> bytes | None:
    fid = _font_key(font)
    if fid not in _notdef_cache:
        _notdef_cache[fid] = _render_char_bytes(font, "￿")
    return _notdef_cache[fid]


def _has_glyph(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    key = (_font_key(font), ch)
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
        result = rendered != notdef and any(rendered)
    if len(_glyph_cache) >= _MAX_GLYPH_CACHE:
        _glyph_cache.clear()
    _glyph_cache[key] = result
    return result


def _font_for_char(base_font: ImageFont.FreeTypeFont, ch: str) -> ImageFont.FreeTypeFont:
    if _has_glyph(base_font, ch):
        return base_font
    for fnt in _fallback_fnts:
        if _has_glyph(fnt, ch):
            return fnt
    return base_font


def _draw_text_fallback(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    base_font: ImageFont.FreeTypeFont,
    fill,
) -> float:
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
        large_radius = min(self.corner_radius, w / 2, h / 2) * scale_factor
        draw.rounded_rectangle(
            [(0, 0), (large_size[0] - 1, large_size[1] - 1)],
            radius=large_radius,
            fill=255,
        )

        mask = mask.resize(size, Image.Resampling.LANCZOS)
        return mask

    def _create_edge_highlight(self, size: tuple[int, int]) -> Image.Image:
        w, h = size
        if self.edge_highlight_intensity <= 0:
            return Image.new("RGBA", size, (255, 255, 255, 0))

        mask = self._create_rounded_mask(size)
        eroded = mask.filter(ImageFilter.MinFilter(9))
        edge = np.maximum(
            np.asarray(mask, dtype=np.float32) - np.asarray(eroded, dtype=np.float32),
            0,
        ) / 255
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        light = 1 - 0.36 * xx / max(w - 1, 1) - 0.64 * yy / max(h - 1, 1)
        light = np.clip(light, 0, 1)
        bright_alpha = np.clip(
            edge * (0.35 + 0.95 * light) * self.edge_highlight_intensity * 255,
            0,
            255,
        ).astype(np.uint8)
        shade_alpha = np.clip(
            edge * (1 - light) * self.edge_highlight_intensity * 120,
            0,
            255,
        ).astype(np.uint8)

        shade = Image.new("RGBA", size, (0, 0, 0, 0))
        shade.putalpha(Image.fromarray(shade_alpha))
        highlight = Image.new("RGBA", size, (255, 255, 255, 0))
        highlight.putalpha(Image.fromarray(bright_alpha))
        return Image.alpha_composite(shade, highlight)

    def _adjust_saturation(self, img: Image.Image, saturation: float) -> Image.Image:
        img_array = np.array(img.convert("RGB"))
        hsv = Image.fromarray(img_array).convert("HSV")
        h, s, v = hsv.split()
        s = Image.fromarray(np.clip(np.array(s) * (saturation / 100), 0, 255).astype(np.uint8))
        return Image.merge("HSV", (h, s, v)).convert("RGB")

    def _chromatic_aberration(self, img: Image.Image, intensity: float) -> Image.Image:
        img_array = np.array(img)
        _, w = img_array.shape[:2]
        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
        offset = max(0, int(round(abs(intensity))))
        if offset == 0:
            return img.convert("RGB")
        positions = np.arange(w)
        r_shifted = r[:, np.clip(positions - offset, 0, w - 1)]
        b_shifted = b[:, np.clip(positions + offset, 0, w - 1)]
        aberration = np.dstack([r_shifted, g, b_shifted])
        return Image.fromarray(aberration.astype(np.uint8))

    def _generate_displacement_map(self, size: tuple[int, int]) -> Image.Image:
        w, h = size
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        center_x = (w - 1) / 2
        center_y = (h - 1) / 2
        half_w = max((w - 1) / 2, 0.5)
        half_h = max((h - 1) / 2, 0.5)
        radius = min(float(self.corner_radius), half_w, half_h)
        qx = np.abs(xx - center_x) - half_w + radius
        qy = np.abs(yy - center_y) - half_h + radius
        outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
        signed_distance = outside + np.minimum(np.maximum(qx, qy), 0) - radius
        normal_y, normal_x = np.gradient(signed_distance)
        normal_length = np.hypot(normal_x, normal_y)
        normal_x = np.divide(
            normal_x,
            normal_length,
            out=np.zeros_like(normal_x),
            where=normal_length > 1e-5,
        )
        normal_y = np.divide(
            normal_y,
            normal_length,
            out=np.zeros_like(normal_y),
            where=normal_length > 1e-5,
        )
        edge_band = max(4, min(w, h) * 0.12)
        edge_strength = np.exp(-np.square(np.maximum(-signed_distance, 0) / edge_band))
        edge_strength[signed_distance > 0] = 0
        disp_r = np.clip(
            np.rint(128 + normal_x * edge_strength * 127), 0, 255
        ).astype(np.uint8)
        disp_g = np.clip(
            np.rint(128 + normal_y * edge_strength * 127), 0, 255
        ).astype(np.uint8)
        disp_b = np.clip(np.rint(edge_strength * 255), 0, 255).astype(np.uint8)
        disp_map = np.dstack([disp_r, disp_g, disp_b])
        return Image.fromarray(disp_map)

    def _apply_displacement(self, img: Image.Image, disp_map: Image.Image, scale: float) -> Image.Image:
        img_array = np.asarray(img.convert("RGB"), dtype=np.float32)
        disp_array = np.asarray(disp_map, dtype=np.float32)
        h, w = img_array.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = np.clip((disp_array[:, :, 0] - 128) / 127, -1, 1) * scale
        dy = np.clip((disp_array[:, :, 1] - 128) / 127, -1, 1) * scale
        sample_x = np.clip(xx - dx, 0, w - 1)
        sample_y = np.clip(yy - dy, 0, h - 1)
        x0 = np.floor(sample_x).astype(np.int32)
        y0 = np.floor(sample_y).astype(np.int32)
        x1 = np.minimum(x0 + 1, w - 1)
        y1 = np.minimum(y0 + 1, h - 1)
        weight_x = sample_x - x0
        weight_y = sample_y - y0
        displaced = np.empty_like(img_array)
        for channel in range(3):
            top = (
                img_array[y0, x0, channel] * (1 - weight_x)
                + img_array[y0, x1, channel] * weight_x
            )
            bottom = (
                img_array[y1, x0, channel] * (1 - weight_x)
                + img_array[y1, x1, channel] * weight_x
            )
            displaced[:, :, channel] = top * (1 - weight_y) + bottom * weight_y
        return Image.fromarray(np.clip(displaced, 0, 255).astype(np.uint8))

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
        edge_mask = np.asarray(disp_map, dtype=np.uint8)[:, :, 2]
        edge_mask = Image.fromarray((edge_mask.astype(np.float32) * 0.55).astype(np.uint8))
        refracted = Image.composite(aberrated, displaced, edge_mask)

        refracted_rgba = refracted.convert("RGBA")
        material_tint = Image.new(
            "RGBA",
            (w, h),
            (0, 0, 0, int(self.white_overlay_opacity * 255))
        )
        glass_with_white = Image.alpha_composite(refracted_rgba, material_tint)

        glass_with_white.putalpha(rounded_mask)

        edge_highlight = self._create_edge_highlight((w, h))
        glass_final = Image.alpha_composite(glass_with_white, edge_highlight)

        result = background_img.convert("RGBA")
        result.paste(glass_final, (x, y), glass_final)

        return result.convert("RGB")

def draw(nickname: str = "Momoi Airi") -> bytes:

    nickname = _resolve("status_nickname", nickname or "Momoi Airi")

    loaded_plugins = nonebot.get_loaded_plugins()

    resources_dir: Path = Path(__file__).parent / "resources"
    bg_dir: Path = bg_img_dir
    candidates = [
        p for p in sorted(bg_dir.iterdir())
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    ] if bg_dir.is_dir() else []
    if not candidates:
        raise FileNotFoundError(f"状态图背景目录内没有可用图片: {bg_dir}")
    bg_img_path: Path = random.choice(candidates)
    mask_img_path: Path = resources_dir / "images" / "airi_status_mask.png"

    with Image.open(bg_img_path).convert("RGBA") as base:
        mask_img = get_image(mask_img_path)
        img = Image.new("RGBA", base.size, (255, 255, 255, 0))
        marker = get_image(marker_img_path)

        base = Image.alpha_composite(base, Image.new("RGBA", base.size, (0, 0, 0, 40)))
        liquid_glass = LiquidGlass(
            displacement_scale=14,
            blur_amount=16,
            saturation=160,
            aberration_intensity=1,
            corner_radius=50,
            edge_highlight_intensity=0.3,
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

        mask_alpha = np.asarray(mask_img.getchannel("A"), dtype=np.uint8)

        def draw_ring(center_x, center_y, ratio, fill):
            ratio = min(1, max(0, float(ratio)))
            if ratio <= 0:
                return
            padding = 60
            left = int(np.floor(center_x - padding))
            top = center_y - padding
            right = int(np.ceil(center_x + padding)) + 1
            bottom = center_y + padding + 1
            alpha = mask_alpha[top:bottom, left:right].astype(np.float32)
            yy, xx = np.mgrid[top:bottom, left:right].astype(np.float32)
            radius = np.hypot(xx - center_x, yy - center_y)
            alpha[(radius < 51.5) | (radius > 59.5)] = 0
            normal_x = np.divide(
                xx - center_x,
                radius,
                out=np.zeros_like(radius),
                where=radius > 0,
            )
            normal_y = np.divide(
                yy - center_y,
                radius,
                out=np.zeros_like(radius),
                where=radius > 0,
            )
            sample_x = np.clip(
                np.rint(xx - left + normal_x).astype(np.int32),
                0,
                right - left - 1,
            )
            sample_y = np.clip(
                np.rint(yy - top + normal_y).astype(np.int32),
                0,
                bottom - top - 1,
            )
            alpha = np.maximum(alpha, alpha[sample_y, sample_x])
            if ratio < 1:
                angle = (np.degrees(np.arctan2(yy - center_y, xx - center_x)) + 90) % 360
                coverage = np.clip((ratio * 360 - angle) / 1.2 + 0.5, 0, 1)
                alpha *= coverage
            ring = Image.new("RGBA", (right - left, bottom - top), fill)
            ring.putalpha(Image.fromarray(np.clip(np.rint(alpha), 0, 255).astype(np.uint8)))
            img.alpha_composite(ring, (left, top))

        draw_ring(212.5, 781, cpu.usage / 100, cpu_color)
        if ram.total > 0:
            draw_ring(211.5, 935, ram.usage / ram.total, ram_color)
        if swap.total > 0:
            draw_ring(211.5, 1089, swap.usage / swap.total, swap_color)
        if disk.total > 0:
            draw_ring(212.5, 1243, disk.usage / disk.total, disk_color)

        content = ImageDraw.Draw(img)
        nick_fnt = baotu_cjk_fnt if _has_cjk(nickname) else baotu_fnt
        nick_y = 595 + (5 if _has_cjk(nickname) else 0)
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
