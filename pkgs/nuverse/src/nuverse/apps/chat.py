"""The ``chat`` app. Placeholder.

TODO: another agent fills this in. Until then ``APP`` is None and the app is
left out of :data:`nuverse.apps.APPS`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import App


__all__ = ["APP"]


APP: App | None = None
