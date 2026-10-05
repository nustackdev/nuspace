"""The panel: one turn's trace, drawn live, in the Cell the trace is kept in.

The one Cell on a chat the model does not write. What the agent is doing is
*about* the agent rather than from it, and it has to read the same way in
every chat and in every turn, so the host draws it and the model cannot vary
it. It is hardcoded on purpose and it is meant to stay that way.

**One panel per turn, and it is the turn's own Cell.** A chat used to keep one
trace that each turn emptied, which meant scrolling back to the first thing
you asked showed you the last thing the agent did. A turn's trace lives in
that turn's display Cell's own state, because a Cell's state is where a Cell's
state goes, so turn one still shows turn one's work a week later.

**It reads its own id and knows nothing else.** There is no subject to
bake into it: the Cell is about itself. :func:`nuspace.agent.chat.submit` appends
one of these per turn, handing it no more than the Plane it is on, and a Cell's
entry point is given its own id by the runtime.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import ops
from nuspace.agent import chat


__all__ = ["COLUMNS", "TRACE_REF", "display", "rows"]


#: What the three columns are called. A row carries which cycle it belongs to,
#: which of the fixed states it is, and the line itself, and a reader tells a
#: work pass from an answer pass by the first of them.
COLUMNS = ("cycle", "state", "what")

#: What the table is called inside the Cell. Ids are unique inside one Cell
#: and nothing wider, so this is free to be the obvious word.
TRACE_REF = "trace"


def rows(cell_id: nu.StrArg) -> nu.Nu:
    """The trace as a table, as a write. Built fresh at each call site.

    One ref holding a list rather than a ref per row: what a turn is doing is
    one value that grows, and a node per line would be a node to mint, root
    and take down again on every move.

    One node in two tree positions is one node, and this one is written on the
    way in and again on every row, so it is a function called at each of those
    two places rather than a term held in a variable.

    Bare: it reads the trace, so its caller brackets it.
    """
    return nustd.ui.TableRef(TRACE_REF).set(
        nu.Dict.of(
            columns=nu.List.of(*[nu.Str(name) for name in COLUMNS]),
            rows=nu.Collect(
                nu.Map(
                    chat.trace_of(cell_id),
                    lambda row: nu.List.of(
                        nu.ToStr(nu.Dict(row).get_item("cycle", "")),
                        nu.ToStr(nu.Dict(row).get_item("kind", "")),
                        nu.ToStr(nu.Dict(row).get_item("text", "")),
                    ),
                )
            ),
        )
    )


def display(cell_id: nu.StrArg) -> nu.Nu:
    """One turn's trace, now and as it grows. The whole term a panel Cell runs.

    Args:
        cell_id: the panel itself, whose state holds the trace. The Cell's own
            ``cell``.

    Returns:
        A Flow that draws the trace and then redraws it forever.

    Notes:
        - The table is written on the way in even when there is nothing in it
          yet. Writing a ref is what ships its chain to the browser and what
          makes the node there, so a table nothing writes has nothing to
          render and would first come into being on the row that was meant to
          fill it.
        - The subscription is the Cell's own state and not the leaf the trace
          is a key in. A child scoped watch never carries to a pool worker: it
          binds, it reports nothing, and nobody on either end is told.
        - Every draw reads the trace in a snapshot of its own, and the
          subscription is bracketed apart, so nothing is held open between
          rows.
    """
    return ops.snapshot(rows(cell_id)) >> nu.ReactForever(
        ops.snapshot(chat.trace_changed(cell_id)),
        ops.snapshot(rows(cell_id)),
    )
