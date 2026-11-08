"""``nuspace.plane``: the ops over ``Space.planes``. Root is the plane ``"root"``.

A plane is a node in the space's tree: its row names its ``parent`` and
lists its ``children`` and ``cells``, and both sides change together. Every
op is a bare term: the caller brackets it, ``nuspace.atomic(...)`` in code
without flows, ``nuspace.bracketed`` in flows. What decides a write is read
in the same term, so under ``atomic`` it lands in the same commit.

Writes raise when they cannot do what they say (:mod:`nuspace.errors`);
reads that may find nothing give NULL or False. Each op's doc gives its cost
in keys touched and what it raises.

Programs write the module in front: ``nuspace.plane.add(...)``.
"""

from __future__ import annotations

from typing import Any

import nu
import nustd.time
from nuspace.errors import Exists, Missing, Refused
from nuspace.shapes.plane import RESERVED, ROOT
from nuspace.shapes.space import Space
from nuspace.utils import MintId, Require, anchor_of, place
from nuspace.utils.checks import (
    anchored,
    key_free,
    key_spelled,
    live,
    refuse,
    text,
    unkey,
    when,
)
from nuspace.utils.tree import no_cycle, subtree


__all__ = [
    "add",
    "exists",
    "move",
    "on_change",
    "on_children_change",
    "remove",
    "remove_key",
    "rename",
    "set_backend",
    "set_icon",
    "set_key",
    "set_meta",
    "title",
]


#: The prefixes an icon is spelled with, a lucide name or an emoji after it.
ICON_PREFIXES = ("lucide:", "emoji:")


def _icon_spelled(icon: nu.StrArg) -> None:
    """A literal icon is ``""`` or a prefix with something after it. A term is stored as it is.

    Raises:
        Refused: At build, a literal icon spelled otherwise.
    """
    if not isinstance(icon, str) or icon == "":
        return
    prefix, _, rest = icon.partition(":")
    if f"{prefix}:" not in ICON_PREFIXES or not rest:
        msg = f"icon {icon!r}: spell it lucide:<name> or emoji:<char>, or '' for none"
        raise Refused(msg)


def _reserved(id: nu.StrArg, system: nu.BoolArg) -> nu.Nu:
    """Refuse an id no new plane may take: root's, ``""``, or a :data:`RESERVED` one for a user plane.

    Raises:
        Refused: A literal at build, a term at run time.
    """
    if isinstance(id, str):
        user = system is False
        if id in (ROOT, "") or (user and id in RESERVED):
            msg = f"plane id {id!r} is reserved"
            raise Refused(msg)
        if system is True or id not in RESERVED:
            return nu.Noop()
    pid = nu.Str(id)
    always = (pid == ROOT).or_(pid == "")
    taken = nu.List.of(*sorted(RESERVED)).contains(pid).and_(nu.Bool(system).not_())
    return refuse(always.or_(taken), Refused, "plane id ", id, " is reserved")


def _not_root(id: nu.StrArg, doing: str) -> nu.Nu:
    """Refuse an op on root. A literal at build.

    Raises:
        Refused: ``id`` is root.
    """
    msg = f"root cannot be {doing}"
    if isinstance(id, str):
        if id == ROOT:
            raise Refused(msg)
        return nu.Noop()
    return refuse(nu.Str(id) == ROOT, Refused, msg)


def _touched(id: nu.StrArg) -> nu.Nu:
    """Stamp a write to the plane's own row on ``modified_at``."""
    return Space.planes[id].modified_at.set(nustd.time.time())


def add(
    id: nu.StrArg | None = None,
    *,
    parent: nu.StrArg = ROOT,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    name: nu.StrArg = "",
    key: nu.StrArg = "",
    icon: nu.StrArg = "",
    backend: nu.StrArg = "",
    system: nu.BoolArg = False,
    spec: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Create a plane with no cells under ``parent``. Create only: an id taken raises.

    One commit: the row, the id in the parent's ``children``, the key in
    ``Space.indexes.plane_keys`` and the id in ``spec_planes[spec].ids``
    when given. Cost: O(1), about 20 keys.

    Args:
        id: Its id. Minted when the op evaluates when absent.
        parent: The plane it hangs under.
        before: A sibling to place it before.
        after: A sibling to place it after. Neither: the end.
        name: Display text only.
        key: An optional handle in key chars (letters, digits, ``_``, ``-``),
            case-sensitive, ``""`` for none.
        icon: ``lucide:<name>``, ``emoji:<char>`` or ``""``.
        backend: What its runs execute on. ``""``: it does not run.
        system: Protected: ``remove`` refuses it. Only a system plane takes
            a :data:`~nuspace.shapes.plane.RESERVED` id.
        spec: The spec it was made from, ``""`` for none.
        meta: The free dict, for programs. nuspace never reads it.
        into: A ref set to the id in the same commit, for a minted one.

    Raises:
        Exists: The id or the key is taken.
        Missing: No parent or anchor with that id.
        Removed: The parent or the anchor is removed.
        Refused: A reserved id (root's, ``""``, or one of
            :data:`~nuspace.shapes.plane.RESERVED` unless ``system``), an
            anchor that is not a sibling, a key that is not key chars, an
            icon spelled wrong. A literal at build.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    _icon_spelled(icon)
    spelled = key_spelled(key, "plane", empty_ok=True)

    def write(pid: nu.StrArg) -> nu.Nu:
        rows = Space.planes
        row = rows[pid]
        siblings = rows[parent].children

        def made(now: nu.ObjectRef) -> nu.Nu:
            return (
                row.name.set(name)
                >> row.key.set(key)
                >> row.icon.set(icon)
                >> row.parent.set(parent)
                >> row.version.set(0)
                >> row.cells.set(nu.Dict.create())
                >> row.children.set(nu.Dict.create())
                >> row.system.set(system)
                >> row.backend.set(backend)
                >> row.spec.set(spec)
                >> row.meta.set(nu.Dict.create() if meta is None else meta)
                >> row.created_at.set(now)
                >> row.modified_at.set(now)
            )

        writes = (
            _reserved(pid, system)
            >> refuse(rows.contains(pid), Exists, "plane ", pid, " exists")
            >> live(rows, parent, "plane")
            >> anchored(siblings, rows, anchor, pid, "plane", text("plane ", parent))
            >> spelled
            >> key_free(Space.indexes.plane_keys, key, None, "plane")
            >> nu.let(nustd.time.time(), made)
            >> place(siblings, pid, before=before, after=after)
            >> when(key, Space.indexes.plane_keys.set_item(key, pid))
            >> when(spec, Space.indexes.spec_planes[spec].ids.set_item(pid, True))
        )
        return writes if into is None else writes >> into.set(pid)

    if id is None:
        return nu.let(MintId("p"), lambda pid: write(nu.Str(pid)))
    return write(id)


def remove(id: nu.StrArg) -> nu.Nu:
    """Remove a plane and everything below it, softly: rows are stamped, kept and readable.

    Stamps ``removed_at`` and ``removed_by=id`` on the plane and on every
    plane and cell below it not removed yet (rows removed earlier keep
    their own stamp), and drops each stamped row's key from the key index
    (the rows keep ``.key``). The plane leaves its parent's ``children``;
    the rows below stay listed where they are, for a restore. The id goes
    into ``Space.indexes.removed``. Writes nothing about runs: the kernel
    stops the live plane runs of what it sees removed.

    Cost: O(subtree), a few keys per plane and cell below.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed already.
        Refused: Root, or a system plane. Root as a literal at build.
    """
    rows = Space.planes
    row = rows[id]
    keys = Space.indexes

    def stamped(now: nu.ObjectRef) -> nu.Nu:
        def plane(p: nu.Str) -> nu.Nu:
            at = rows[p]
            return (
                at.removed_at.set(now) >> at.removed_by.set(id) >> unkey(keys.plane_keys, at.key, p)
            )

        def cell(c: nu.Str) -> nu.Nu:
            at = Space.cells[c]
            return (
                at.removed_at.set(now) >> at.removed_by.set(id) >> unkey(keys.cell_keys, at.key, c)
            )

        return subtree(id, plane, cell)

    return (
        _not_root(id, "removed")
        >> live(rows, id, "plane")
        >> refuse(row.system.fallback(False), Refused, "plane ", id, " is a system plane")
        >> rows[row.parent].children.del_item(id)
        >> nu.let(nustd.time.time(), stamped)
        >> keys.removed.set_item(id, True)
    )


def move(
    id: nu.StrArg,
    *,
    parent: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Move a plane under a new parent, or to a new spot among its siblings when ``parent`` is left out.

    Before or after a sibling there, or at the end when neither is given.
    The key and everything below it stay as they are. Cost: O(1) writes,
    about 10 keys, plus O(depth) reads for the cycle check, which climbs
    from the new parent to root.

    Raises:
        Missing: No plane, new parent or anchor with that id.
        Removed: The plane, the new parent or the anchor is removed.
        Refused: Root, a cycle, an anchor that is not a sibling there.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    rows = Space.planes
    row = rows[id]
    target = row.parent if parent is None else parent
    checks = _not_root(id, "moved") >> live(rows, id, "plane")
    if parent is not None:
        checks = checks >> live(rows, parent, "plane") >> no_cycle(id, parent)
    siblings = rows[target].children
    return (
        checks
        >> anchored(siblings, rows, anchor, id, "plane", text("plane ", target))
        >> rows[row.parent].children.del_item(id)
        >> place(siblings, id, before=before, after=after)
        >> row.parent.set(target)
        >> _touched(id)
    )


def rename(id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a plane's name, display text only. Cost: O(1), 2 keys.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
    """
    return live(Space.planes, id, "plane") >> Space.planes[id].name.set(name) >> _touched(id)


def set_key(id: nu.StrArg, key: nu.StrArg) -> nu.Nu:
    """Set a plane's key, or change it: the old entry out of ``plane_keys``, the new one in.

    Cost: O(1), about 5 keys.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Exists: Another plane holds the key.
        Refused: An empty key, or one not in key chars. A literal at build.
    """
    spelled = key_spelled(key, "plane", empty_ok=False)
    index = Space.indexes.plane_keys
    row = Space.planes[id]
    old = row.key.fallback("")
    return (
        spelled
        >> live(Space.planes, id, "plane")
        >> key_free(index, key, id, "plane")
        >> nu.IfDo((old != "").and_(old != key), index.del_item(old))
        >> index.set_item(key, id)
        >> row.key.set(key)
        >> _touched(id)
    )


def remove_key(id: nu.StrArg) -> nu.Nu:
    """Drop a plane's key: out of ``plane_keys``, ``.key`` cleared, free for other planes.

    Cost: O(1), 3 keys.

    Raises:
        Missing: No plane with that id, or it has no key.
        Removed: It is removed.
    """
    row = Space.planes[id]
    return (
        live(Space.planes, id, "plane")
        >> refuse(row.key.fallback("") == "", Missing, "plane ", id, " has no key")
        >> Space.indexes.plane_keys.del_item(row.key)
        >> row.key.set("")
        >> _touched(id)
    )


def set_icon(id: nu.StrArg, icon: nu.StrArg) -> nu.Nu:
    """Set a plane's icon: ``lucide:<name>``, ``emoji:<char>`` or ``""``. Cost: O(1), 2 keys.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Refused: A literal icon spelled otherwise, at build.
    """
    _icon_spelled(icon)
    return live(Space.planes, id, "plane") >> Space.planes[id].icon.set(icon) >> _touched(id)


def set_backend(id: nu.StrArg, backend: nu.StrArg) -> nu.Nu:
    """Set what a plane's runs execute on. Live runs keep theirs. Cost: O(1), 2 keys.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Refused: Root, which never runs. A literal at build.
    """
    return (
        _not_root(id, "given a backend")
        >> live(Space.planes, id, "plane")
        >> Space.planes[id].backend.set(backend)
        >> _touched(id)
    )


def set_meta(id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a plane's free meta dict, shallow. Cost: O(fields).

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
    """
    return live(Space.planes, id, "plane") >> Space.planes[id].meta.update(fields) >> _touched(id)


def exists(id: nu.StrArg, *, removed: bool = False) -> nu.Bool:
    """Whether a plane with this id is in the space: a row, not removed. A read, never raises.

    ``removed=True`` counts removed rows as well. Cost: O(1), 2 point reads.
    """
    there = Space.planes.contains(id)
    return there if removed else there.and_(Space.planes[id].removed_at.exists().not_())


def title(id: nu.StrArg) -> nu.Str:
    """What a list or a header shows for a plane: its name, else its id. Cost: O(1), 2 reads.

    Removed planes keep theirs.

    Raises:
        Missing: No plane with that id.
    """
    name = Space.planes[id].name.fallback("")
    shown = nu.If(name == "", id, name)
    return nu.Str(Require(Space.planes.contains(id), shown, text("no plane ", id), exc_cls=Missing))


def on_change(id: nu.StrArg) -> nu.Nu:
    """A watch over a plane's whole row: every slot at any depth. One kv subscription.

    Fires on its name, icon, meta, removal, its ``version`` (so on every
    write to one of its cells), and its ``cells`` and ``children`` lists. A
    child's own row sits outside this prefix, so a child rename does not
    fire it; a child added, moved or removed does. Never raises.
    """
    return Space.planes[id].on_change()


def on_children_change(id: nu.StrArg) -> nu.Nu:
    """A watch over a plane's ``children`` list only. One kv subscription.

    Fires when a child is added, moved in or out, reordered or removed. Not
    on a child's own row: a rename is that child's :func:`on_change`. Never
    raises.
    """
    return Space.planes[id].children.on_change()
