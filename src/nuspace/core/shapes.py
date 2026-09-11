"""Nuspace top shapes.

Two orchestration surfaces live under one ``Space``:

- ``apps``  - a **flat** dict of apps. Single depth, no folders.
- ``pages`` - the root ``Page``. Pages nest recursively (a page holds
  child pages) and each page holds its own dict of sections. The root
  page is a real page: it may carry sections of its own.

An app and a section are the same substance (a ``nu.prog`` program: a
python module whose ``out`` entry point returns a Nu tree). They differ
only in the ``policy`` string that says when to run.
For v0 the policy is a bare string; a richer tagged form can come later
without changing the shape layout.

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
from nu.domains.shape.dsl import SlotDescriptor
from nuspace.core.refs import AppsRef, PagesRef, SectionsRef


__all__ = ["App", "Page", "Section", "Space"]


class App(nu.Shape):
    """One ops-orchestration unit. Same substance as a ``Section``.

    ``snippet`` is a ``ProgramRef``, exactly like ``Section.snippet``:
    the stored text is source in ``nu.prog``'s sense, a module with an
    ``out`` entry point whose signature is the scope contract. nuspace
    binds one value, ``path``, and for an app it is ``"apps.<app_id>"``.

    Unlike a section, ``path`` is **not** a ui mount prefix. An app is
    headless -- it produces, a page displays -- so it has nowhere to
    mount a ui ref and must not try. ``path`` is a kv namespace: the
    app's own corner of ``Space.state``, collision-free by construction.

    ``policy`` is metadata, and for v1 nothing reads it: every app runs
    always. It stays in the shape because the policy engine slots in
    behind it, not beside it.
    """

    name = nu.kv.StrRef.slot()
    snippet = nu.kv.ProgramRef.slot()
    policy = nu.kv.StrRef.slot()


class Section(nu.Shape):
    """One block on a page. Always a Nu program, no exceptions.

    ``snippet`` is a ``ProgramRef``, so the stored text is source in
    ``nu.prog``'s sense: a module with an ``out`` entry point whose
    signature is the scope contract. nuspace offers one scope value,
    ``path``, and it is ``"sections.<section_id>"``. Reading the slot
    yields the source verbatim; ``.load()`` / ``.run()`` come with the
    ref.

    ``tpl`` is **provenance, not type**. It says what produced the
    snippet -- ``program`` (arbitrary, the person wrote it) or ``text``
    (the wysiwyg template) -- and nothing branches on it to decide
    whether the block compiles, runs or is supervised. Every block does
    all three. See :mod:`nuspace.core.tpl` for the registry, the tiers
    and where a templated block keeps its content.

    ``order`` is the block's position on the page. Dict-keyed sections
    sort by ``mint_ordered_id`` (creation time) by default, which is
    right until someone drags one; ``order`` is what makes reordering
    expressible. The Pages driver renormalizes it to ``index * 10``
    after every structural change.
    """

    name = nu.kv.StrRef.slot()
    snippet = nu.kv.ProgramRef.slot()
    policy = nu.kv.StrRef.slot()
    tpl = nu.kv.StrRef.slot()
    order = nu.kv.IntRef.slot()


class Page(nu.Shape):
    """A page: a title, a bag of sections, and nested child pages.

    ``pages`` is stapled on after the class body because a class body
    cannot mention its own not-yet-defined class.
    """

    title = nu.kv.StrRef.slot()
    sections = SectionsRef.slot(Section)


# Recursive self-slot: mint the Slot after Page exists, then register it
# both in ``_slots`` and as a descriptor so ``Page.pages`` reads like any
# other slot from Python-side.
_pages_slot = PagesRef.slot(Page)
_pages_slot.name = "pages"
_pages_slot._owner_cls = Page
Page._slots["pages"] = _pages_slot
Page.pages = SlotDescriptor("pages", _pages_slot)


class Space(nu.Shape):
    """Nuspace root.

    ``apps`` is a flat dict, not a tree. v0 rooted it at a group shape
    that nested recursively, mirroring ``Page``; nothing ever used the
    nesting and it cost every apps call site a path walk. A page tree
    earns its depth because a page is a place you navigate to. An app is
    a running program in a list, so ``Space.apps["a_x"].snippet`` is the
    whole address and the group layer is gone.
    """

    apps = AppsRef.slot(App)
    pages = nu.kv.ShapeRef.slot(Page)
    state = nu.kv.DictRef.slot(str)
