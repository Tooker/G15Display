"""Save all seven actual dashboard pages plus the menu, without opening USB."""

from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont

from g15display.dashboard import Dashboard, PAGES, TITLES
from g15display.sources import Sources


def main():
    sources = Sources()
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            sources.poll()
            time.sleep(0.05)
        for name, snapshot in sources.snapshots.items():
            print(f"{name}: {snapshot.error or 'OK'}")
        ui = Dashboard(sources)
        sheet = Image.new("RGB", (1320, 840), (20, 25, 34))
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default(size=16)
        for index in range(8):
            ui.menu = index == 7
            ui.page = 0 if ui.menu else index
            frame = ui.render()
            panel = Image.new("RGB", frame.size, (127, 182, 223))
            panel.paste((12, 30, 48), mask=frame.convert("L"))
            panel = panel.resize((640, 172), Image.Resampling.NEAREST)
            x, y = 10 + (index % 2) * 660, 8 + (index // 2) * 210
            draw.text((x, y), "MENU" if ui.menu else TITLES[index], font=font, fill="white")
            sheet.paste(panel, (x, y + 25))
        path = Path("previews/dashboard.png")
        path.parent.mkdir(exist_ok=True)
        sheet.save(path)
        print(path.resolve())
    finally:
        sources.close()


if __name__ == "__main__":
    main()
