"""A fixed 5 x 7 pixel alphabet for a one-bit LCD, with one blank column.

Rows are five-bit masks. No outline rasterisation or fractional positioning is
involved. Lowercase is displayed as uppercase; German umlauts use AE/OE/UE.
"""

from functools import lru_cache
import unicodedata

from PIL import Image


ROWS = {
    " ": "00 00 00 00 00 00 00",
    "A": "0E 11 11 1F 11 11 11", "B": "1E 11 11 1E 11 11 1E",
    "C": "0E 11 10 10 10 11 0E", "D": "1E 11 11 11 11 11 1E",
    "E": "1F 10 10 1E 10 10 1F", "F": "1F 10 10 1E 10 10 10",
    "G": "0E 11 10 17 11 11 0F", "H": "11 11 11 1F 11 11 11",
    "I": "0E 04 04 04 04 04 0E", "J": "07 02 02 02 12 12 0C",
    "K": "11 12 14 18 14 12 11", "L": "10 10 10 10 10 10 1F",
    "M": "11 1B 15 15 11 11 11", "N": "11 19 15 13 11 11 11",
    "O": "0E 11 11 11 11 11 0E", "P": "1E 11 11 1E 10 10 10",
    "Q": "0E 11 11 11 15 12 0D", "R": "1E 11 11 1E 14 12 11",
    "S": "0F 10 10 0E 01 01 1E", "T": "1F 04 04 04 04 04 04",
    "U": "11 11 11 11 11 11 0E", "V": "11 11 11 11 11 0A 04",
    "W": "11 11 11 15 15 1B 11", "X": "11 11 0A 04 0A 11 11",
    "Y": "11 11 0A 04 04 04 04", "Z": "1F 01 02 04 08 10 1F",
    "0": "0E 11 13 15 19 11 0E", "1": "04 0C 04 04 04 04 0E",
    "2": "0E 11 01 02 04 08 1F", "3": "1E 01 01 0E 01 01 1E",
    "4": "02 06 0A 12 1F 02 02", "5": "1F 10 10 1E 01 01 1E",
    "6": "06 08 10 1E 11 11 0E", "7": "1F 01 02 04 08 08 08",
    "8": "0E 11 11 0E 11 11 0E", "9": "0E 11 11 0F 01 02 0C",
    ".": "00 00 00 00 00 0C 0C", ",": "00 00 00 00 0C 0C 08",
    ":": "00 0C 0C 00 0C 0C 00", ";": "00 0C 0C 00 0C 0C 08",
    "-": "00 00 00 1F 00 00 00", "_": "00 00 00 00 00 00 1F",
    "/": "01 02 02 04 08 08 10", "\\": "10 08 08 04 02 02 01",
    "%": "19 19 02 04 08 13 13", "+": "00 04 04 1F 04 04 00",
    "=": "00 00 1F 00 1F 00 00", "!": "04 04 04 04 04 00 04",
    "?": "0E 11 01 02 04 00 04", "<": "02 04 08 10 08 04 02",
    ">": "08 04 02 01 02 04 08", "(": "02 04 08 08 08 04 02",
    ")": "08 04 02 02 02 04 08", "[": "0E 08 08 08 08 08 0E",
    "]": "0E 02 02 02 02 02 0E", "'": "04 04 08 00 00 00 00",
    '"': "0A 0A 0A 00 00 00 00", "&": "0C 12 14 08 15 12 0D",
    "*": "00 15 0E 1F 0E 15 00", "#": "0A 1F 0A 0A 1F 0A 00",
    "|": "04 04 04 04 04 04 04", "@": "0E 11 17 15 17 10 0E",
}


def lcd_text(text):
    text = str(text).replace("\n", " ").replace("\r", " ")
    for original, replacement in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
                                   ("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE"),
                                   ("ß", "ss"), ("–", "-"), ("—", "-"),
                                   ("’", "'"), ("‘", "'"), ("“", '"'),
                                   ("”", '"'), ("…", "...")):
        text = text.replace(original, replacement)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).upper()
    return "".join(c if c in ROWS else "?" for c in text)


@lru_cache(maxsize=256)
def _mask(text, scale):
    image = Image.new("1", (max(1, (len(text) * 6 - 1) * scale), 7 * scale))
    pixels = image.load()
    for index, char in enumerate(text):
        for y, row in enumerate(ROWS[char].split()):
            value = int(row, 16)
            for x in range(5):
                if value & (1 << (4 - x)):
                    for dy in range(scale):
                        for dx in range(scale):
                            pixels[(index * 6 + x) * scale + dx, y * scale + dy] = 1
    return image


class PixelFont:
    def __init__(self, scale=1):
        self.scale = scale

    def width(self, text):
        return max(0, len(lcd_text(text)) * 6 - 1) * self.scale

    def draw(self, draw, xy, text, fill=1):
        text = lcd_text(text)
        if text:
            draw.bitmap(xy, _mask(text, self.scale), fill=fill)


SMALL = PixelFont()
LARGE = PixelFont(2)
