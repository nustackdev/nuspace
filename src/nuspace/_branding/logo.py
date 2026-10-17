"""The mark, as terminal braille glyphs: purple top left, blue bottom right.

Baked once from the source PNG, a 2x4 sub-pixel braille packing. The art is
still the Nu mark, kept until nuspace has one of its own.
"""

from __future__ import annotations

from rich.text import Text

from .palette import BLUE, PURPLE


__all__ = ["WIDTH", "logo"]


_COLOR = {"P": PURPLE, "B": BLUE}

# 16 cols x 8 rows; each row is (glyphs, per glyph color tag: 'P' purple,
# 'B' blue, '.' blank).
_LOGO: tuple[tuple[str, str], ...] = (
    ("⠀⢀⣤⣶⣾⣿⣿⣿⣿⣿⣿⡇⠀⢰⣿⣿", ".PPPPPPPPPPP.PPB"),
    ("⣰⣿⣿⠟⠋⠉⠉⠉⠉⣿⣿⡇⠀⢸⣿⣿", "PPPPPPPPPPPP.BBB"),
    ("⣿⣿⡇⠀⠀⣀⣀⠀⠀⣿⣿⡇⠀⢸⣿⣿", "PPP..PP..PPB.BBB"),
    ("⣿⣿⡇⠀⢸⣿⣿⠀⠀⣿⣿⡇⠀⢸⣿⣿", "PPP.PPP..BBB.BBB"),
    ("⣿⣿⡇⠀⢸⣿⣿⠀⠀⣿⣿⡇⠀⢸⣿⣿", "PPP.PPP..BBB.BBB"),
    ("⣿⣿⡇⠀⢸⣿⣿⠀⠀⠉⠉⠀⠀⢸⣿⣿", "PPP.PBB..BB..BBB"),
    ("⣿⣿⡇⠀⢸⣿⣿⣀⣀⣀⣀⣠⣴⣿⣿⠏", "PPP.BBBBBBBBBBBB"),
    ("⣿⣿⠇⠀⢸⣿⣿⣿⣿⣿⣿⡿⠿⠛⠁⠀", "PBB.BBBBBBBBBBB."),
)

#: Every row is this many glyphs wide.
WIDTH = len(_LOGO[0][0])


def logo() -> Text:
    """The mark, eight rows of :data:`WIDTH` glyphs."""
    text = Text()
    for i, (chars, colors) in enumerate(_LOGO):
        if i:
            text.append("\n")
        for char, tag in zip(chars, colors, strict=True):
            text.append(char, style=_COLOR.get(tag, ""))
    return text
