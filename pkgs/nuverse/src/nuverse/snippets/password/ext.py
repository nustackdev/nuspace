"""The password snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "password",
    "Password generator",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A strong password, drawn again whenever its length or characters change.",
    group="Examples",
    icon="key",
)
