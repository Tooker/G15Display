"""Build the Apple Silicon .app including its own Python runtime and native UI."""

import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from g15display.pixelfont import PixelFont


def icon():
    path = ROOT / "assets"
    path.mkdir(exist_ok=True)
    image = Image.new("RGBA", (1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 60, 964, 964), radius=205, fill=(24, 31, 42), outline=(61, 83, 104), width=12)
    draw.rounded_rectangle((140, 220, 884, 615), radius=44, fill=(127, 182, 223), outline=(9, 17, 26), width=24)
    font = PixelFont(22)
    font.draw(draw, ((1024 - font.width("G15")) // 2, 338), "G15", fill=(12, 30, 48))
    for index in range(4):
        x = 220 + index * 156
        draw.rounded_rectangle((x, 700, x + 114, 774), radius=18, fill=(109, 142, 167))
    draw.ellipse((785, 142, 827, 184), fill=(131, 212, 169))
    image.save(path / "G15.icns")


def main():
    icon()
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "pyinstaller-cache")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
                    str(ROOT / "G15 Display.spec")], cwd=ROOT, env=env, check=True)
    print(f"App erstellt: {ROOT / 'dist' / 'G15 Display.app'}")


if __name__ == "__main__":
    main()
