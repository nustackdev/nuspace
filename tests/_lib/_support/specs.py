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

#: A cell that appends a line every second while its pane follows the end:
#: the pane's scroll, driven from a cell (``nuspace.web.pane()``). Add it from
#: the ``/`` menu (``Tail``) in a space run with ``NUSPACE_TESTING=1``.
TAIL_SRC = """\
import nu
import nustd.ui
import nuspace.web as web

lines = nustd.ui.ListRef("lines")


def tick(i):
    return lines.append(nu.Str("line ") + nu.Format(i)) >> nu.Delay(1.0)


def out():
    return lines.clear() >> web.pane().follow("bottom") >> nu.ForRangeDo(1, 100_000, tick)
"""

#: A cell that keeps a dropped image in the space's blob store and shows it:
#: the upload intake, the worker's upload view, the blob store and its
#: mount, end to end. Add it from the ``/`` menu (``Snap``) in a space run
#: with ``NUSPACE_TESTING=1``.
SNAP_SRC = """\
import nu
import nustd.ui
import nuspace


class Snap(nustd.ui.Column):
    drop = nustd.ui.UploadFileRef.slot(accept="image/*", prompt="Drop an image")
    pic = nustd.ui.ImageRef.slot(fit="contain", radius="md", zoom=True)
    note = nustd.ui.TextRef.slot(value="")


def show(bid):
    return (
        Snap.pic.set_src(nuspace.blobs.url(bid))
        >> Snap.pic.set_download(nuspace.blobs.url(bid, download=True))
        >> Snap.note.set("Kept as " + nu.Str(bid))
    )


def store(f):
    put = nuspace.Blobs.put_stream(Snap.drop.open(), mime=f["mime"], name=f["name"])
    return Snap.note.set("Storing...") >> nu.let(show, bid=put)


def picked():
    return nu.IfDo(nu.IsNull(Snap.drop), nu.Noop(), nu.let(lambda f: store(nu.Dict(f)), f=Snap.drop))


def out():
    return nu.ReactEvery(Snap.drop.on_change(), lambda _: picked())
"""

PLANES = (
    PlaneSpec("plain", "Plain", web=WebOptions(), backend="async"),
    PlaneSpec(
        "jobs", "Jobs", icon="list", cells=(("list", TEXT_SRC),), web=WebOptions(), backend="mp"
    ),
)

CELLS = (
    CellSpec("text", "Text", TEXT_SRC, classes=("prose",), default_for=("prose",)),
    CellSpec("program", "Program", "def out():\n    return nu.Noop()\n"),
    CellSpec("tail", "Tail", TAIL_SRC, description="Appends a line a second, the pane following."),
    CellSpec("snap", "Snap", SNAP_SRC, description="Keeps a dropped image in the blob store."),
)

CONTENTS = (
    ContentSpec(NoteContent, description="A note: its body, its stars, done or not."),
    ContentSpec(PlainContent, label="Plain note"),
)
