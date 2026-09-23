"""The ``monaco`` snippet. Placeholder.

TODO: another agent fills this in. Until then ``SOURCE`` is empty,
``SNIPPET`` is None and the snippet is left out of
:data:`nuverse.snippets.SNIPPETS`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = ""

SNIPPET: Snippet | None = None
