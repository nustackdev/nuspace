"""Nuspace top shapes.

Two orchestration surfaces live under one ``Space``:

- ``apps``  - a **flat** dict of apps. Single depth, no folders.
- ``pages`` - the root ``Page``. Pages nest recursively (a page holds
  child pages) and each page holds its own dict of sections. The root
  page is a real page: it may carry sections of its own.

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
``Section`` would need the page path too. See :mod:`nuspace.core.tpl`.
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

    ``apps`` is a flat dict, not a tree. v0 rooted it at a group shape
    that nested recursively, mirroring ``Page``; nothing ever used the
    nesting and it cost every apps call site a path walk. A page tree
    earns its depth because a page is a place you navigate to. An app is
    a running program in a list, so ``Space.apps["a_x"].snippet`` is the
    whole address and the group layer is gone.
    """

    apps = nu.kv.ShapesDictRef.slot(App)
    pages = nu.kv.ShapeRef.slot(Page)
    state = nu.kv.DictRef.slot(str)
