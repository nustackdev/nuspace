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

from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
import nustd.time
from nuspace.errors import Exists, Missing, Refused
from nuspace.shapes.plane import RESERVED, ROOT, UNTITLED
from nuspace.shapes.space import Space
from nuspace.utils import MintId, Require, anchor_of, place
from nuspace.utils.checks import (
    anchored,
    id_spelled,
    key_free,
    key_spelled,
    live,
    refuse,
    removed_alone,
    text,
    unkey,
    when,
)
from nuspace.utils.tree import no_cycle, subtree


if TYPE_CHECKING:
    from nuspace.shapes.cell import Cell
    from nuspace.shapes.plane import Plane


__all__ = [
    "add",
    "exists",
    "keyed",
    "move",
    "on_change",
    "on_children_change",
    "remove",
    "remove_key",
    "rename",
    "restore",
    "set_backend",
    "set_icon",
    "set_key",
    "set_meta",
    "title",
    "transfer",
]


#: The prefixes an icon is spelled with, a lucide name or an emoji after it.
ICON_PREFIXES = ("lucide:", "emoji:")

#: The icon a plane is made with when none is given.
DEFAULT_ICON = "lucide:file-text"


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


def _reserved(id: nu.StrArg) -> nu.Nu:
    """Refuse an id no plane may take: root's or ``""``.

    Raises:
        Refused: A literal at build, a term at run time.
    """
    if isinstance(id, str):
        if id in (ROOT, ""):
            msg = f"plane id {id!r} is reserved"
            raise Refused(msg)
        return nu.Noop()
    pid = nu.Str(id)
    return refuse((pid == ROOT).or_(pid == ""), Refused, "plane id ", id, " is reserved")


def _key_reserved(key: nu.StrArg, system: nu.BoolArg) -> nu.Nu:
    """Refuse a :data:`RESERVED` key for a plane that is not system.

    Raises:
        Refused: A literal at build, a term at run time.
    """
    if isinstance(key, str) and isinstance(system, bool):
        if key in RESERVED and not system:
            msg = f"plane key {key!r} is reserved"
            raise Refused(msg)
        return nu.Noop()
    taken = nu.List.of(*sorted(RESERVED)).contains(key).and_(nu.Bool(system).not_())
    return refuse(taken, Refused, "plane key ", key, " is reserved")


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


def _told(event: str) -> nu.Nu:
    """Queue ``event`` once the term runs. Imported here: importing nuspace reaches no telemetry."""
    from nuspace._telemetry.usage import track

    return track(event)


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

    One commit: the row, the id in the parent's ``children`` (the parent's
    ``modified_at`` stamped), the key in
    ``Space.indexes.plane_keys`` and the id in ``spec_planes[spec].ids``
    when given. Told to telemetry as made by nuspace, from a spec or by
    hand, reading no key. Cost: O(1), about 20 keys.

    Args:
        id: Its id, key chars. Minted when the op evaluates when absent.
        parent: The plane it hangs under.
        before: A sibling to place it before.
        after: A sibling to place it after. Neither: the end.
        name: Display text only.
        key: An optional handle in key chars (letters, digits, ``_``, ``-``),
            case-sensitive, ``""`` for none.
        icon: ``lucide:<name>`` or ``emoji:<char>``. ``""``: :data:`DEFAULT_ICON`.
        backend: What its runs execute on. ``""``: it does not run.
        system: Protected: ``remove`` refuses it. Only a system plane holds
            a :data:`~nuspace.shapes.plane.RESERVED` key.
        spec: The spec it was made from, ``""`` for none.
        meta: The free dict, for programs. nuspace never reads it.
        into: A ref set to the id in the same commit, for a minted one.

    Raises:
        Exists: The id or the key is taken.
        Missing: No parent or anchor with that id.
        Removed: The parent or the anchor is removed.
        Refused: A reserved id (root's or ``""``), a
            :data:`~nuspace.shapes.plane.RESERVED` key unless ``system``, an
            id or a key that is not key chars, an anchor that is not a
            sibling, an icon spelled wrong. A literal at build.
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
                >> row.icon.set(icon or DEFAULT_ICON if isinstance(icon, str) else icon)
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
            _reserved(pid)
            >> id_spelled(pid, "plane")
            >> refuse(rows.contains(pid), Exists, "plane ", pid, " exists")
            >> live(rows, parent, "plane")
            >> anchored(siblings, rows, anchor, pid, "plane", text("plane ", parent))
            >> spelled
            >> _key_reserved(key, system)
            >> key_free(Space.indexes.plane_keys, key, None, "plane")
            >> nu.let(nustd.time.time(), made)
            >> place(siblings, pid, before=before, after=after)
            >> _touched(parent)
            >> when(key, Space.indexes.plane_keys.set_item(key, pid))
            >> when(spec, Space.indexes.spec_planes[spec].ids.set_item(pid, True))
        )
        writes = writes if into is None else writes >> into.set(pid)
        return writes >> told

    from nuspace._telemetry.usage import created  # importing nuspace reaches no telemetry

    told = created("plane", system=system, spec=spec)
    if id is None:
        return nu.let(MintId("p"), lambda pid: write(nu.Str(pid)))
    return write(id)


def remove(id: nu.StrArg) -> nu.Nu:
    """Remove a plane and everything below it, softly: rows are stamped, kept and readable.

    Stamps ``removed_at`` and ``removed_by=id`` on the plane and on every
    plane and cell below it not removed yet (rows removed earlier keep
    their own stamp), and drops each stamped row's key from the key index
    (the rows keep ``.key``). The plane leaves its parent's ``children``
    (the parent's ``modified_at`` stamped);
    the rows below stay listed where they are, for a restore. The id goes
    into ``Space.indexes.removed``. Writes nothing about runs: the kernel
    stops the live plane runs of what it sees removed. Each plane and cell
    stamped is told to telemetry.

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
                at.removed_at.set(now)
                >> at.removed_by.set(id)
                >> unkey(keys.plane_keys, at.key, p)
                >> _told("plane_removed")
            )

        def cell(c: nu.Str) -> nu.Nu:
            at = Space.cells[c]
            return (
                at.removed_at.set(now)
                >> at.removed_by.set(id)
                >> unkey(keys.cell_keys, at.key, c)
                >> _told("cell_removed")
            )

        return subtree(id, plane, cell)

    return (
        _not_root(id, "removed")
        >> live(rows, id, "plane")
        >> refuse(row.system.fallback(False), Refused, "plane ", id, " is a system plane")
        >> rows[row.parent].children.del_item(id)
        >> _touched(row.parent)
        >> nu.let(nustd.time.time(), stamped)
        >> keys.removed.set_item(id, True)
    )


def restore(id: nu.StrArg) -> nu.Nu:
    """Bring back a plane removed by itself, and everything that went with it.

    Takes back what :func:`remove` wrote: the plane goes last in its
    parent's ``children`` (the parent's ``modified_at`` stamped), and every
    plane and cell below it stamped by this removal gets its stamps erased
    and its key indexed again. Rows removed before by themselves stay
    removed (they are not listed below it). The id leaves
    ``Space.indexes.removed``. Runs are not touched: the kernel stopped the
    old ones, an open pane starts a new one. Each plane and cell brought
    back is told to telemetry.

    Cost: O(subtree), a few keys per plane and cell below.

    Raises:
        Missing: No plane with that id.
        Refused: It is not removed, or it went with a plane above it (restore that one).
        Removed: Its parent is removed.
        Exists: Another row took one of the subtree's keys since. Nothing is written.
    """
    rows = Space.planes
    row = rows[id]
    keys = Space.indexes

    def mine(at: Plane | Cell) -> nu.Bool:
        return at.removed_by.fallback("") == id

    def free(index: nustd.kv.DictRef, at: Plane | Cell, own: nu.Str, what: str) -> nu.Nu:
        return nu.IfDo(mine(at), key_free(index, at.key.fallback(""), own, what))

    def back(index: nustd.kv.DictRef, at: Plane | Cell, own: nu.Str, event: str) -> nu.Nu:
        key = at.key.fallback("")
        return nu.IfDo(
            mine(at),
            when(key, index.set_item(key, own))
            >> at.removed_at.erase()
            >> at.removed_by.erase()
            >> _told(event),
        )

    checked = subtree(
        id,
        lambda p: free(keys.plane_keys, rows[p], p, "plane"),
        lambda c: free(keys.cell_keys, Space.cells[c], c, "cell"),
    )
    restored = subtree(
        id,
        lambda p: back(keys.plane_keys, rows[p], p, "plane_restored"),
        lambda c: back(keys.cell_keys, Space.cells[c], c, "cell_restored"),
    )
    return (
        removed_alone(rows, id, "plane")
        >> live(rows, row.parent, "plane")
        >> checked
        >> place(rows[row.parent].children, id)
        >> _touched(row.parent)
        >> restored
        >> keys.removed.del_item(id)
    )


def move(
    id: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Move a plane among its siblings: before or after one, or to the end. Same parent.

    Writes the parent's ``children`` order and stamps the parent's
    ``modified_at``; the plane's own row is not written. Another parent is
    :func:`transfer`. Cost: O(1), about 4 keys.

    Raises:
        Missing: No plane or anchor with that id.
        Removed: The plane or the anchor is removed.
        Refused: Root, an anchor that is not a sibling, or the plane itself.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    rows = Space.planes
    row = rows[id]
    siblings = rows[row.parent].children
    return (
        _not_root(id, "moved")
        >> live(rows, id, "plane")
        >> anchored(siblings, rows, anchor, id, "plane", text("plane ", row.parent))
        >> siblings.del_item(id)
        >> place(siblings, id, before=before, after=after)
        >> _touched(row.parent)
    )


def transfer(
    id: nu.StrArg,
    parent: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Transfer a plane under another parent: before or after a child there, or at the end.

    One commit: out of the old parent's ``children``, into the new one's,
    ``parent`` set, ``modified_at`` stamped on the plane and on both
    parents. Everything below rides along as it is: cells, children, keys,
    state, spec. Runs are untouched. Cost: O(1) writes, about 10 keys,
    plus O(depth) reads for the cycle check, which climbs from the new
    parent to root.

    Raises:
        Missing: No plane, new parent or anchor with that id.
        Removed: The plane, the new parent or the anchor is removed.
        Refused: Root, the same parent (that is :func:`move`), a system
            plane, a system parent other than root, a cycle, an anchor
            that is not a child of the new parent.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    rows = Space.planes
    row = rows[id]
    old = row.parent
    siblings = rows[parent].children
    system_parent = (nu.Str(parent) != ROOT).and_(rows[parent].system.fallback(False))
    checks = (
        _not_root(id, "transferred")
        >> live(rows, id, "plane")
        >> live(rows, parent, "plane")
        >> refuse(nu.Str(parent) == old, Refused, "plane ", id, " is under ", parent, " already")
        >> refuse(row.system.fallback(False), Refused, "plane ", id, " is a system plane")
        >> refuse(system_parent, Refused, "plane ", parent, " is a system plane")
        >> no_cycle(id, parent)
        >> anchored(siblings, rows, anchor, id, "plane", text("plane ", parent))
    )
    # The old parent is read off the row, so everything about it comes before the row moves.
    moved = (
        rows[old].children.del_item(id)
        >> _touched(old)
        >> place(siblings, id, before=before, after=after)
        >> row.parent.set(parent)
        >> _touched(parent)
        >> _touched(id)
    )
    return checks >> moved


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
        Refused: An empty key, or one not in key chars, a literal at build.
            A :data:`~nuspace.shapes.plane.RESERVED` key on a plane that is
            not system.
    """
    spelled = key_spelled(key, "plane", empty_ok=False)
    index = Space.indexes.plane_keys
    row = Space.planes[id]
    old = row.key.fallback("")
    return (
        spelled
        >> live(Space.planes, id, "plane")
        >> _key_reserved(key, row.system.fallback(False))
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


def keyed(key: nu.StrArg) -> nu.Str:
    """The id of the live plane holding ``key``, ``""`` when none does. A read. Cost: O(1), 1 point read."""
    return nu.Str(Space.indexes.plane_keys.get_item(key, ""))


def title(id: nu.StrArg) -> nu.Str:
    """What a list or a header shows for a plane: its name, else ``Untitled``. Cost: O(1), 2 reads.

    Removed planes keep theirs.

    Raises:
        Missing: No plane with that id.
    """
    name = Space.planes[id].name.fallback("")
    shown = nu.If(name == "", UNTITLED, name)
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
