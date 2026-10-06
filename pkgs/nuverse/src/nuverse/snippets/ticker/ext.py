"""The ticker snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "ticker",
    "Ticker",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A stat tile counting the seconds its plane was open.",
    group="Examples",
    icon="timer",
)
