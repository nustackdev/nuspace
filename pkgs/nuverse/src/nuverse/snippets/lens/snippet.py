"""A lens: a shape in the store, browsed as cascading columns."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.ui.lens


if TYPE_CHECKING:
    import nu


__all__ = ["out"]


def out(shape: type, prefix: nu.Ref | None = None) -> nu.Nu:
    """Browse ``shape`` at ``prefix``, for as long as the cell runs.

    Args:
        shape: A shape class: what the lens expects to find.
        prefix: A ref: where in the store that shape lives. None means the root.
    """
    lens = nustd.ui.lens.LensRef("lens")
    return nustd.ui.lens.browse(lens, shape, prefix=prefix)
