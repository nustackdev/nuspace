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

``agent`` and ``chat`` are the third and fourth, and they are two slots
rather than one because they are two things. ``agent`` is a *run*: one task
and nuagent's working memory for it. ``chat`` is what was *said*, and it is on
the agent's own surface -- the model speaks by emitting a program that appends
to it, which is the same primitive as every other thing it does. Both live in
their own packages under the same one-way rule.

``state`` is the scratch kv namespace snippets write to, one ``Scratch``
row per running thing. Per ``model.md`` nuspace has no state pillar --
state is Nu's kv fabric -- but a bare ``nu.kv.StrRef("foo")`` carries no
owner Shape, so it never resolves against a ``tags=(Space,)`` navigator.
``Space.state[section]`` gives a snippet a reachable row without minting a
shape per value, and it is a ref chain rather than a key someone built out
of a prefix and a dot, so one block naming another's row is ordinary
navigation.

It is also where a templated block keeps its content: a text block's
markdown lives at ``Space.state[sid].data["text"]``, because the ids are
all a snippet's scope carries and a slot on ``Section`` would need the page
id too. See :mod:`nuspace.core.tpl`.
"""

from __future__ import annotations

import nu

# One way only: neither submodule's shapes may import back from here. They
# import nu alone, so this edge cannot deadlock whichever way the package is
# entered, and nothing in this package depends on import order any more.
from nuspace.agent.shapes import Agent
from nuspace.apps.shapes import App
from nuspace.chat.shapes import Chat
from nuspace.pages.shapes import Page, Section


__all__ = ["Agent", "App", "Chat", "Page", "Scratch", "Section", "Space"]


class Scratch(nu.Shape):
    """One running thing's own corner of the space's kv. A section or an app.

    Keyed by the id of whatever is running, which is why section ids are
    globally unique rather than unique per page: an app and a section are the
    same substance and share one namespace here.

    Two slots, because the two have different writers. ``data`` is the
    snippet's, and it may hold anything it likes; ``error`` is nuspace's, and
    it is what the status a browser reads is made of, so a snippet cannot
    clobber it by naming a key.
    """

    data = nu.kv.DictRef.slot(str)
    error = nu.kv.StrRef.slot()


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
    state = nu.kv.ShapesDictRef.slot(Scratch)
    # Both singular, not dicts: nuagent runs one task at a time, so one slot
    # each is the true statement and a dict keyed by run id would be a shape
    # describing a concurrency the loop does not have.
    agent = nu.kv.ShapeRef.slot(Agent)
    # Top level, not nested under `agent`, because it is not the agent's
    # property. Anything in the space may post here -- a cron job, an app, a
    # person at a REPL -- and the sidebar cannot tell which did.
    chat = nu.kv.ShapeRef.slot(Chat)
