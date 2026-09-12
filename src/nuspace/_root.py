"""Which space root class a call addresses, resolved at call time.

``core.shapes`` imports the per-submodule shapes to build ``Space``, so a
submodule that named ``Space`` at import time would close the cycle. This is
the one place the import is deferred instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace.core import Space


__all__ = ["resolve_root"]


def resolve_root(root: type[Space] | None) -> type[Space]:
    """``root``, or ``Space`` when it is None.

    ``Space.apps`` and ``DemoSpace.apps`` are different addresses, so an op
    against a subclassed space has to be told which root it is working.

    Args:
        root: the space's root Shape class, or None for the stock ``Space``.
    """
    if root is not None:
        return root
    # Deferred on purpose: see the module docstring.
    from nuspace.core.shapes import Space

    return Space
