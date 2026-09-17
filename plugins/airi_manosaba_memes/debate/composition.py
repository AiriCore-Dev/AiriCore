import io

from PIL import Image

from ..drawer import draw_trial


def compose_trial(base: bytes, overlay: bytes) -> bytes:
    with Image.open(io.BytesIO(base)) as source:
        canvas = source.convert("RGBA")
    with Image.open(io.BytesIO(overlay)) as source:
        foreground = source.convert("RGBA")
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", canvas.size, (0, 0, 0, 128)))
    width = round(foreground.width * canvas.height / foreground.height)
    foreground = foreground.resize((width, canvas.height), Image.Resampling.LANCZOS)
    canvas.alpha_composite(foreground, (canvas.width - width, 0))
    result = io.BytesIO()
    canvas.save(result, "PNG")
    return result.getvalue()


def render_debate_trial(request, character, options) -> bytes:
    from .rendering import render_debate

    return compose_trial(render_debate(request), draw_trial(character, options, transparent=True))
