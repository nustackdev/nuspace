"""The specs the tests register, through the installed ``nuspace-testing`` package (``tests/_ext``).

Registered, each is named ``testing.<name>``: ``testing.plain``,
``testing.text``, ``testing.Note``. A space registers only what installed
packages add, so a test wanting a Plane, a Cell or a kind of its own adds it
here and opens the space with ``extensions=["testing"]``.
"""

from __future__ import annotations

from nuspace.specs import CellSpec, ContentSpec, PlaneSpec, WebOptions

from .contents import NoteContent, PlainContent


#: The prog a text-like test cell runs.
TEXT_SRC = "def out():\n    return prose()\n"

PLANES = (
    PlaneSpec("plain", "Plain", web=WebOptions(), backend="async"),
    PlaneSpec(
        "jobs", "Jobs", icon="list", cells=(("list", TEXT_SRC),), web=WebOptions(), backend="mp"
    ),
)

CELLS = (
    CellSpec("text", "Text", TEXT_SRC, classes=("prose",), default_for=("prose",)),
    CellSpec("program", "Program", "def out():\n    return nu.Noop()\n"),
)

CONTENTS = (
    ContentSpec(NoteContent, description="A note: its body, its stars, done or not."),
    ContentSpec(PlainContent, label="Plain note"),
)
