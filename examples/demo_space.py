"""This demo space's own shape.

A space that needs storage nuspace core does not ship subclasses ``Space``
rather than growing core. ``ShapeMeta`` rebinds ``_root_shape`` on every
slot including the inherited ones, so ``DemoSpace`` is the root for all of
them and the whole shape resolves against one navigator.

Its own module, not ``demo.py``, on purpose. ``demo.py`` runs as a script,
so it is ``__main__``; a block doing ``from demo import DemoSpace`` would
re-import it under a second module name and get a *different* class object
than the one the navigator is tagged with. Blocks and the host have to name
the same class, so it lives somewhere both import the same way.
"""

from __future__ import annotations

import nu
from nuspace.core.shapes import Space


__all__ = ["DemoSpace", "Series"]


class Series(nu.Shape):
    """One named, append-only numeric series.

    ``Space.state`` is the scratch namespace for a value; this is the
    scratch namespace for a *sequence* of them. ``Kh57Ref`` is what makes
    it worth having: the map can hold billions of entries and a chart
    still asks for a bounded reservoir sample over a key range instead of
    reading it all back.

    ``cursor`` is the next key to write. A slot rather than a computed
    length, because the producer appends without reading the map back and
    the sampler needs the range's upper bound anyway.
    """

    points = nu.kv.Kh57Ref.slot(int)
    cursor = nu.kv.IntRef.slot()


class DemoSpace(Space):
    """Space plus this demo's own series storage."""

    series = nu.kv.ShapesDictRef.slot(Series)


# Where the worker resolves its scope from. The worker takes this as
# config precisely so a subclassed root works out of process too: a worker
# that assumed ``Space`` would address the parent's slots and silently
# read an empty store.
SCOPE_SPEC = "demo_space:DemoSpace"
