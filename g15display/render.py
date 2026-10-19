"""Content is separate from USB, so screens can later use a Rust transport."""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from .display import WIDTH, HEIGHT
from .pixelfont import SMALL, LARGE


def text_screen(text: str) -> Image.Image:
    """Draw up to four lines; overlong lines are clipped at the right edge."""
    lines = text.split("\n")
    if len(lines) > 4:
        raise ValueError("Das Display bietet Platz für maximal vier Textzeilen.")
    image = Image.new("1", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        SMALL.draw(draw, (1, 1 + index * 10), line)
    return image


def clock_screen(now: datetime | None = None) -> Image.Image:
    now = now or datetime.now().astimezone()
    image = Image.new("1", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    SMALL.draw(draw, (1, 1), "LOGITECH G15")
    draw.line((0, 11, WIDTH - 1, 11), fill=1)
    LARGE.draw(draw, (1, 14), now.strftime("%H:%M:%S"))
    SMALL.draw(draw, (1, 34), now.strftime("%d.%m.%Y"))
    return image


def save_preview(image: Image.Image, path: Path):
    """Blue LCD-like preview, enlarged without smoothing; no USB access."""
    preview = Image.new("RGB", image.size, (127, 182, 223))
    preview.paste((12, 30, 48), mask=image.convert("L"))
    preview.resize((WIDTH * 5, HEIGHT * 5), Image.Resampling.NEAREST).save(path, format="PNG")
