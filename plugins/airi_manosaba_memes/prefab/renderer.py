from typing import TYPE_CHECKING

from sketchbook import Bitmap, Drawer, FontSet, Layer, SpriteMode

from ..asset_cache import get_bitmap
from .models import BlendMode

if TYPE_CHECKING:
    from .synthesizer import Prefab


SPRITE_MODES = {
    BlendMode.NORMAL: SpriteMode.Normal,
    BlendMode.MULTIPLY: SpriteMode.Multiply,
    BlendMode.OVERLAY: SpriteMode.Overlay,
    BlendMode.SOFT_LIGHT: SpriteMode.SoftLight,
}


class SketchbookRenderer:


    def __init__(self, prefab: "Prefab") -> None:
        self.prefab = prefab

    def render(self, nodes: set[int]) -> bytes:

        return self._render_transformed(
            nodes,
            canvas_size=self.prefab._sprite_size,
            offset=(0.0, 0.0),
            scale_factor=1.0,
        )

    def render_view(
        self,
        nodes: set[int],
        crop_box: tuple[int, int, int, int],
        target_size: tuple[int, int],
    ) -> bytes:

        crop_left, crop_top, crop_right, crop_bottom = crop_box
        crop_width = crop_right - crop_left
        crop_height = crop_bottom - crop_top
        target_width, target_height = target_size
        if crop_width <= 0 or crop_height <= 0:
            raise ValueError("crop box must have positive dimensions")
        if target_width <= 0 or target_height <= 0:
            raise ValueError("target size must have positive dimensions")

        scale_factor = min(
            1.0,
            target_width / crop_width,
            target_height / crop_height,
        )
        offset = (
            (target_width - crop_width * scale_factor) / 2 - crop_left * scale_factor,
            (target_height - crop_height * scale_factor) / 2 - crop_top * scale_factor,
        )
        if self.prefab._character_data.flatten_before_resize:
            width, height = self.prefab._sprite_size
            layer = Layer("prefab").sprite_exact(
                Bitmap.load(self.render(nodes)),
                position=offset,
                target_size=(width * scale_factor, height * scale_factor),
            )
            return Drawer(*target_size, FontSet()).layer(layer).render()
        return self._render_transformed(
            nodes,
            canvas_size=target_size,
            offset=offset,
            scale_factor=scale_factor,
        )

    def _render_transformed(
        self,
        nodes: set[int],
        *,
        canvas_size: tuple[int, int],
        offset: tuple[float, float],
        scale_factor: float,
    ) -> bytes:
        width, height = self.prefab._sprite_size
        layer = Layer("prefab")
        has_sprites = False

        for node_id, scale, coordinates in self.prefab._layers:
            if node_id not in nodes or node_id not in self.prefab._available_image_ids:
                continue

            node = self.prefab._character_data.nodes[node_id]
            sprite = node.sprite
            image_width, image_height = self.prefab._image_sizes[node_id]
            left = width - coordinates[0] - image_width * scale[0] / 2
            top = height - coordinates[1] - image_height * scale[1] / 2

            bitmap = get_bitmap(self.prefab._get_sprite_path(node.name))

            layer = layer.sprite_exact(
                bitmap,
                position=(
                    offset[0] + left * scale_factor,
                    offset[1] + top * scale_factor,
                ),
                target_size=(
                    image_width * scale[0] * scale_factor,
                    image_height * scale[1] * scale_factor,
                ),
                mode=SPRITE_MODES[sprite.blend_mode] if sprite else SpriteMode.Normal,
                color=sprite.color if sprite else (1.0, 1.0, 1.0, 1.0),
                cutoff=sprite.cutoff if sprite else 0.0,
                stencil_read=sprite.stencil_read if sprite else None,
                stencil_write=sprite.stencil_write if sprite else None,
            )
            has_sprites = True

        drawer = Drawer(*canvas_size, FontSet())
        if has_sprites:
            drawer.layer(layer)
        return drawer.render()
