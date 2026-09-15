"""The chat driver: one ``ReactForever`` arm per interaction, all in parallel.

The whole web layer for the agent, and flat like the other three. Every arm is
one subscription wired to one thing, and nothing in it branches. Two families,
and an arm belongs to exactly one:

- **browser -> kv.** A ``ChatRef`` event fires; the arm runs one
  :mod:`nuspace.agent.ops` call over the event's own fields.
- **kv -> browser.** The conversation or the run changed; the arm ships one
  ``set_chat`` carrying the whole current answer.

**Nothing here reaches into the runner.** A submit writes the task and bumps
the nonce; the runner is subscribed to the same store and hears it. Same
separation the apps driver has, and it is why the surface works in a process
with no runner in it at all: you can type, the write lands, and nothing runs
until something is there to run it.

**Two state arms, one per slot.** What the sidebar shows comes off two shapes:
the conversation is ``Space.chat`` and the run behind it is ``Space.agent``.
Neither subsumes the other -- an app can append a message with no run going,
and a run advances turns without saying anything -- so there are two arms and
each ships the whole frame. A kv subscription is depth-unbounded, so one turn
ships several identical-shaped frames as its slots land one after another.
Wasteful, not wrong: every frame carries the whole current answer.

**Every arm is long-lived by construction.** The ws endpoint races the
connection against this tree and closes the socket when either finishes, so a
tree that completes drops the browser. What keeps that true is
:mod:`nuspace.web.arms`, shared with the other three drivers. Arm names are
prefixed ``chat_`` so a composition holding all four cannot have two arms
binding one attrs key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.kv
from nuspace._root import resolve_root
from nuspace.agent import ops
from nuspace.chat import ops as chat_ops
from nuspace.web.arms import Arms, field_str


if TYPE_CHECKING:
    import nu
    from nu.domains.shape import Shape
    from nuspace.web.chat.ref import ChatRef


__all__ = ["ARMS", "chat_driver"]


#: How many arms the composition folds. Pinned so a new interaction that
#: forgets its arm, or an arm that quietly loses its subscription, says so.
ARMS = 4


#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("chat")


def chat_driver(chat: ChatRef, *, root: type[Shape] | None = None) -> nu.Nu:
    """The agent sidebar, live, as one tree. Built per connection.

    Args:
        chat: the ``ChatRef`` on the mounted shell, already bound so its wire
            path resolves. Structural, so that path is the bare slot name.
        root: the space's root Shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never
        finishes, which is the contract the ws endpoint holds it to.
    """
    root = resolve_root(root)

    # Built per use, never bound once and dropped into two arms: a Nu node is
    # a value, and one object sitting in two tree positions is one compiled
    # node the two arms then share at runtime.
    def frame() -> nu.Nu:
        return chat.set_chat(
            chat_ops.messages_of(root=root),
            status=ops.status_of(root=root),
            task=ops.task_of(root=root),
            turns=ops.turns_of(root=root),
            error=ops.error_of(root=root),
        )

    # A cold store has no agent slot, and a subscription over a missing shape
    # resolves to INVALID and silently never fires. The runner boots through
    # `init_agent` too; this is the half that keeps a tab self-sufficient in a
    # process where no runner was mounted at all.
    boot = chat_ops.init_chat(root=root) >> ops.init_agent(root=root) >> frame()

    flow = (
        # -- browser -> kv ---------------------------------------------------
        _arms.event(
            "chat_submit",
            chat.on_submit(),
            ops.submit(field_str("chat_submit", "text"), root=root),
        )
        | _arms.event("chat_reset", chat.on_reset(), ops.reset(root=root))
        # -- kv -> browser ---------------------------------------------------
        # Two arms over two slots, because the surface draws on two. The
        # conversation moves when anything appends -- the agent, an app, the
        # composer -- and the run moves on its own schedule underneath. One
        # arm watching only `agent` is what made the sidebar sit still while
        # a cron job talked into it.
        #
        # One fresh subscription per arm, never a shared term: two arms
        # holding one Changed node would share one handle, and the first of
        # them to end would close it under the other.
        | _arms.state("chat_said", root.chat.on_change(), frame())
        | _arms.state("chat_run", root.agent.on_change(), frame())
    )
    return nustd.kv.auto_flow_atomic(boot >> flow, scope=root)
