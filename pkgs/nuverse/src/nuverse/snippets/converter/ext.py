"""The converter snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "converter",
    "Unit converter",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Length, mass, temperature and time: type on either side, the other follows.",
    group="Examples",
    icon="calculator",
)
