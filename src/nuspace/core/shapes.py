"""Nuspace top shapes.

Two orchestration surfaces live under one ``Space``, and both are **flat**
dicts keyed by id:

- ``apps``  - every app in the space. Single depth, no folders.
- ``pages`` - every page in the space. The tree is data, not storage
  depth: a page carries its ``parent`` and its ordered ``children``, so
  any page is one lookup away and a browser route addresses it directly.

An app and a section are the same substance (a ``nu.prog`` program: a
python module whose ``out`` entry point returns a Nu tree). They differ
only in the ``policy`` string that says when to run. ``App`` lives in
:mod:`nuspace.apps.shapes` and ``Page`` / ``Section`` in
:mod:`nuspace.pages.shapes`, each beside the runner and the ops that work
it. Both are re-exported here, since ``Space`` is where they meet.

``state`` is the scratch kv namespace snippets write to. Per ``model.md``
nuspace has no state pillar -- state is Nu's kv fabric -- but a bare
``nu.kv.StrRef("foo")`` carries no owner Shape, so it never resolves
against a ``tags=(Space,)`` navigator. ``Space.state["<key>"]`` gives
snippets a reachable slot without minting a shape per value.

It is also where a templated block keeps its content: a text block's
markdown lives at ``Space.state["sections.<sid>.text"]``, because
``path`` is the only thing a snippet's scope carries and a slot on
``Section`` would need the page id too. See :mod:`nuspace.core.tpl`.
"""

from __future__ import annotations

import nu

# One way only: neither submodule's shapes may import back from here. They
# import nu alone, so this edge cannot deadlock whichever way the package is
# entered, and nothing in this package depends on import order any more.
from nuspace.apps.shapes import App
from nuspace.pages.shapes import Page, Section


__all__ = ["App", "Page", "Section", "Space"]


class Space(nu.Shape):
    """Nuspace root.

    Neither container nests. v0 rooted apps at a recursive group shape and
    pages at a recursive ``Page``, which cost every call site a path walk
    and fixed a page's depth the moment its address was built. Depth is a
    relation, so it lives in ``Page.parent`` / ``Page.children`` and both
    dicts are one level deep.
    """

    apps = nu.kv.ShapesDictRef.slot(App)
    pages = nu.kv.ShapesDictRef.slot(Page)
    state = nu.kv.DictRef.slot(str)
