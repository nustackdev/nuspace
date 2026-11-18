"""Store: one store of a space, as a record: its root shape and its init. Only what is the data's own.

The core stores are declared in :mod:`nuspace.shapes.stores`, a device's
beside its shapes (the web device: :mod:`nuspace.web.stores`). The
record sits here, with the roots, so the assemblies and the devices both
read it and neither imports the other for it. A store has no ops of its
own: its init term is the one thing it runs, and the store's declaration
builds it.

Where a store lives (its file, its backend, its notify channel) is not
here: an assembly decides it (``nuspace.space.local.layout``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu


__all__ = ["Store"]


@dataclass(frozen=True)
class Store:
    """One store of a space: its root shape and its init.

    Attributes:
        root: The root shape, also the tag its navigator is bound under.
        init: Builds the bare term that makes the store's fixed containers.
    """

    root: type[nu.Shape]
    init: Callable[[], nu.Nu]
