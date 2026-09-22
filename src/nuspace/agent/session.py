"""A turn's working memory, in the store, under the chat whose turn it is.

:class:`~nuspace.agent.shapes.Session` says what the slots are. This says
where they live and how to read one back without the read collapsing.

**Scoping is the whole difficulty, and nuspace does not solve it for free.**
A Shape's slots address by name and by nothing else, so two chats running at
once would both write ``messages`` at the root of the store and stamp on each
other. A Cell's program does get its bare refs rooted under the Cell, but only
its *ui* refs: the rewrite asks :func:`nuspace.web.utils.rooted` about every
chain and passes by everything that is not a ``nustd.ui`` ref, which is
exactly what keeps a Cell's store writes off the browser's tree and is not
negotiable. So a bare session inside a chat stays bare, addressed at the root
of the store and tagged by its own class, and it fails two different ways
depending on where it runs: in the main process the tagged lookup finds no
Navigator and raises, and in a worker, where both proxies are bound untagged
so one pool can serve any Space, it resolves by fallback and quietly writes to
the root. The second one is the collision, and it is the one nothing would
report.

The nesting is therefore spelled out here: the session hangs off the talking
Cell's own node, which makes the address per chat and the tag ``Space`` like
every other ref in nuspace, because a ref takes both off the parent it was
built under.

**Beside ``state`` rather than inside it**, and that is load bearing twice.
The conversation lives in ``state`` and :func:`nuspace.ops.chat.changed` wakes
the chat on that container, so a session kept in there would wake the chat on
every write a pass makes about itself. And the two are different substances:
``state`` is what a chat *is*, and this is machinery one turn left behind.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.agent.shapes import Session
from nuspace.agent.source import FENCE
from nuspace.ops.utils import atomic
from nuspace.shapes import Space


__all__ = [
    "SESSION",
    "answer_of",
    "changed",
    "cleared",
    "drawn_cell_of",
    "outcome_of",
    "passes_of",
    "reply_of",
    "said_line_of",
    "session_of",
]


#: What the session is kept under, on the talking Cell. A sibling of ``state``
#: and of ``prog``, and a name no Shape declares: :class:`~nuspace.shapes.Cell`
#: names the slots nuspace itself reads, and nothing there reads this one.
SESSION = "session"

#: What the answer cycle's pass puts the Cell's source under.
CELL = "cell"

#: And the line the conversation keeps.
SAID = "said"


def session_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """This chat's session, as the ref its slots hang off.

    A ref rather than the Shape class: the slots descend off either the same
    way, and only a ref can say *where*.

    Built fresh per term rather than held in a variable across them, the same
    discipline every address in :mod:`nuspace.ops.chat` keeps. One node in two
    tree positions is one node, and :func:`changed` hands this one to a
    subscription, which is a handle the first holder to end closes under the
    other.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that talks.
        root: the Space shape class. The parent carries it, so every slot
            underneath resolves against the same store as the rest of nuspace
            without being told.
    """
    return nustd.kv.ShapeRef(
        SESSION,
        shape_type=Session,
        parent_ref=root.planes[plane_id].cells[cell_id],
    )


def _floored(leaf: nu.Nu) -> nu.Nu:
    """One of the session's string slots, empty where nothing has written it.

    Every string read here goes through this. An unwritten leaf reads EMPTY
    and every Query that touches EMPTY collapses to INVALID, which writes
    nothing and raises nothing, so the failure would be a panel that silently
    stops growing rather than anything anybody could find.
    """
    return nu.Str(nu.If(leaf.exists(), nu.Str(leaf), nu.Str("")))


def reply_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What the model said this pass, in sentences. Not the program it wrote.

    A reply is prose and then a fenced block, and the block is the action. This
    is the other half, which is the part addressed to a person. Taken as
    everything before the first fence, so a reply that is all code reads empty
    and a reply with no code at all reads whole.

    Uncut. How much of it fits belongs to whoever draws it, and a reader that
    clipped would leave nowhere to ask for the whole thing.
    """
    reply = _floored(session_of(plane_id, cell_id, root=root).reply)
    return nu.Str(nu.List(reply.split(nu.Str(FENCE)))[nu.Int(0)]).strip()


def outcome_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What running the model's program came to, this pass.

    Five things wear this one slot, because to the model they are one thing:
    the yield of a program that ran, the diagnostic of a module that would not
    build, the message for a reply carrying no code, the error of a program
    that built and then raised, and the complaint about an answer that would
    not stand up. Every one of them is the next pass's input, which is the
    whole of how a model fixes itself.
    """
    return _floored(session_of(plane_id, cell_id, root=root).outcome)


def passes_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """How many passes the cycle running now has taken. Zero before the first.

    The loop's own counter, read rather than kept twice. It is incremented at
    the head of a pass, so anything reading it inside one is reading the pass
    it is in and can say so without adding one.
    """
    passes = session_of(plane_id, cell_id, root=root).passes
    return nu.Int(nu.If(passes.exists(), nu.Int(passes), nu.Int(0)))


def answer_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What the answer cycle's last pass handed back, empty before there is one.

    Floored the same way a string slot is, and for the same reason: an
    unwritten dict leaf reads EMPTY, and every ``get_item`` over EMPTY
    collapses, so the whole answer would read INVALID rather than absent.
    """
    held = session_of(plane_id, cell_id, root=root).answer
    return nu.Dict(nu.If(held.exists(), nu.Dict(held), nu.Dict.of()))


def drawn_cell_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The source of the Cell the answer cycle wants drawn. ``""`` for none."""
    return nu.ToStr(answer_of(plane_id, cell_id, root=root).get_item(nu.Str(CELL), nu.Str("")))


def said_line_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The line the conversation keeps for that answer. ``""`` for none."""
    return nu.ToStr(answer_of(plane_id, cell_id, root=root).get_item(nu.Str(SAID), nu.Str("")))


def changed(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A fresh subscription that fires on everything a turn writes about itself.

    The session's own container and not a slot in it. A child scoped watch
    never carries to a pool worker: it binds, it reports nothing, and nobody
    on either end is told. The container above carries, and this is that
    container.

    Separate from :func:`nuspace.ops.chat.changed`, which watches the Cell's
    ``state``, so a reader can have what was *said* without also waking on
    every observation a pass fed back to the model.

    Nothing nuspace ships subscribes to this: a turn's panel reads the trace
    on the Plane that draws. This is here for a Cell somebody writes that
    wants the raw working memory, and it is the one correct spelling of that
    address.
    """
    return session_of(plane_id, cell_id, root=root).on_change()


def cleared(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Empty the slots one turn leaves behind, so the next starts on its own.

    A turn that skipped this would be a turn showing the last one's sentences
    for as long as its first model call took, and an answer cycle that started
    holding the last turn's answer would draw it again.

    ``messages`` is not here because the turn sets it outright, and ``passes``
    is not because each cycle zeroes it. What is left is the slots a pass only
    ever overwrites, which is the same thing said one turn too late.

    Written empty rather than erased: an erase on a leaf nothing wrote raises,
    and every chat's first turn clears before it has ever had a pass.

    Guarded on the Cell and bracketed as one commit, for the reasons the
    writes in :mod:`nuspace.ops.chat` are: a write under a key nobody made
    makes one, and six commits is six notifications for one fact.
    """
    cells = root.planes[plane_id].cells
    session = session_of(plane_id, cell_id, root=root)
    return atomic(
        nu.IfDo(
            cells.contains(cell_id),
            session.reply.set(nu.Str(""))
            >> session.draft.set(nu.Str(""))
            >> session.outcome.set(nu.Str(""))
            >> session.observation.set(nu.Str(""))
            >> session.answer.set(nu.Dict.of())
            >> session.drawn.set(nu.Bool(False)),
        ),
        root,
    )
