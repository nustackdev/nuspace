"""What Home's cells share, settings too: the stores, a page, the space's name, the versions.

The stores they read, a page's link, the space's name and path, the
versions this process runs, and the shaping helpers. Reads are bare nu terms, bracketed by the caller. Shaping is plain Python
over plain data, run as a host call once the read is done: it never reads a
store. Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import nu
import nustd.ui
from nuspace.shapes import Space

from ..interactions import IconName
from ..ops import href


__all__ = [
    "HISTORY",
    "LIVE",
    "VERSIONS",
    "Compact",
    "Head",
    "SpaceName",
    "SpaceWhere",
    "compact",
    "ids",
    "page",
    "title",
    "version",
]


#: Every run ever, by plane. Read one plane's list at a time.
HISTORY = Space.exec.indexes.history

#: What runs now.
LIVE = Space.exec.indexes.live


def ids(held: nu.Nu) -> nu.List:
    """The keys of a dict ref, ``[]`` when it was never made. O(its keys)."""
    return nu.List(nu.If(held.exists(), nu.list(held.keys()), []))


def title(plane: nu.StrArg) -> nu.Str:
    """A plane's title: its name, else its id. 1 read."""
    name = Space.planes[plane].name.fallback("")
    return nu.Str(nu.If(name == "", plane, name))


def page(plane: nu.StrArg) -> nu.Dict:
    """A plane as a page shows it: ``{id, title, icon, href}``. Icon and title only, no parents.

    The title is the plane's name, else its id. Cost: O(1), 2 reads.
    """
    return nu.Dict.of(
        id=plane,
        title=title(plane),
        icon=IconName(Space.planes[plane].icon.fallback("")),
        href=href(plane),
    )


def compact(n: object) -> str:
    """A count as Home writes it: full digits to 9,999, compact past (``18.4K``, ``1.2M``)."""
    value = int(n or 0)
    if value < 10_000:
        return f"{value:,}"
    for size, unit in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= size:
            shown = f"{value / size:.1f}".removesuffix(".0")
            return f"{shown}{unit}"
    return f"{value:,}"  # pragma: no cover


#: ``Compact(n)``: :func:`compact` as a term.
Compact = nu.host(compact, name="HomeCompact")


def version(dist: str) -> str:
    """An installed distribution's version, ``""`` when it is not installed."""
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return ""


#: ``{label: version}`` of what this process runs, read once as the module is imported:
#: a running term does not ask importlib. nu ships as the ``nucore`` distribution.
VERSIONS = {"nuspace": version("nuspace"), "nu": version("nucore")}


def _name(path: object) -> str:
    text = str(path or "").rstrip("/")
    return Path(text).name if text else "Throwaway store"


def _where(path: object) -> str:
    text = str(path or "")
    home = str(Path.home())
    return "~" + text[len(home) :] if text == home or text.startswith(home + "/") else text


#: ``SpaceName(path)``: the space's name, its directory's base name.
SpaceName = nu.host(_name, name="HomeSpaceName")

#: ``SpaceWhere(path)``: the path with the home directory as ``~``.
SpaceWhere = nu.host(_where, name="HomeSpaceWhere")


class Head(nustd.ui.Row):
    """A subsection's head, under a section's title: its own title, and how many it shows."""

    title = nustd.ui.HeadingRef.slot(level=3)
    count = nustd.ui.TextRef.slot(size="sm", tone="muted")
