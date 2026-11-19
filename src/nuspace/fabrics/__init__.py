"""``nuspace.fabrics``: what a space reaches outside itself through, as nu fabrics, beside nustd's.

A fabric is not an assembly block: it knows no space, no layout and no
driver. It is a backend bound on the Context, a Ref reading it, and the
terms that act through that Ref, the way ``nustd.fs`` is one.

- :mod:`.browser`: a browser tab opened on a url, once a server answers.

Namespaced: ``from nuspace.fabrics import browser``.
"""

from . import browser


__all__ = ["browser"]
