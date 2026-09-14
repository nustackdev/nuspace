"""``ChatRef`` -- the agent sidebar as one nu.ui Ref.

A component ref like ``AppsRef`` or ``LensRef``, and the narrowest of the
four: a transcript, a status, and a box to type in. Same two halves, built out
of the same :mod:`nuspace.web.wire` idiom.

- **Events**, browser -> server. Two ops, each on its own wire path under
  ``<ref>.ops.``. The path is the discrimination, so the driver binds one arm
  per op rather than switching on a string in a payload.
- **Writes**, server -> browser. One op, ``set_chat``, on the ref's own path,
  tagged with ``op`` -- the browser slice is registered per mount path and a
  write to a path with no slice is dropped.

The ref holds no state and reads nothing. What a submit means in kv is
:mod:`nuspace.agent.ops`, and which op is wired to which arm is
:mod:`nuspace.web.chat.driver`.

**It mounts on the Shell, not on a Screen.** The agent is not a surface you
navigate to, it is a thing that is there while you work on whichever surface
you are on, so it is a structural slot beside ``NavRef`` and the browser
renders it as a pinned rail on every route. That is also why there is no
selection and no route here: there is one agent and one conversation.

**Two stores behind one frame.** ``messages`` comes off :mod:`nuspace.chat`,
which is the conversation and is append-only; ``status`` and ``turns`` come off
:mod:`nuspace.agent`, which is the run behind it. The surface shows one thing
because a person reading it is watching one thing, but they are two slots and
either changes without the other: a run advances a turn having said nothing,
and an app can post a message with no run in sight.

**One frame carries the whole answer.** There is no append op and no delta.
A frame is a snapshot of both slots, so a browser that missed one is never
left holding a conversation it cannot be corrected on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.ui.core import Changed, Ref
from nuspace.web.wire import event, write


if TYPE_CHECKING:
    from nu.lang import IntArg, ListArg, Nu, StrArg


__all__ = ["ChatRef"]


class ChatRef(Ref):
    """One agent conversation, and the box that starts the next one."""

    _wire_type_override = "ChatRef"

    # --- writes: server -> browser -------------------------------------------

    def set_chat(
        self,
        messages: ListArg[dict],
        *,
        status: StrArg,
        task: StrArg,
        turns: IntArg,
        error: StrArg,
    ) -> Nu:
        """Replace the whole sidebar: the conversation and where the run is.

        Args:
            messages: the conversation, one ``{role, text}`` dict per message,
                oldest first. ``role`` is ``user``, ``agent`` or ``system``.
                Straight off ``Space.chat`` -- what was said, by whoever wrote
                it. The run's own transcript is not this and is not shipped:
                the model's reply text is reasoning, and reasoning is not an
                answer.
            status: ``idle`` / ``running`` / ``done`` / ``stopped`` / ``failed``.
            task: the prompt this run is answering.
            turns: how many turns it has spent.
            error: what killed the loop, or ``""``. Not the model's mistakes --
                those are messages, because that is what they are to it.
        """
        return write(
            self,
            "set_chat",
            messages=messages,
            status=status,
            task=task,
            turns=turns,
            error=error,
        )

    # --- events: browser -> server -------------------------------------------

    def on_submit(self) -> Changed:
        """``{text}``. The human asked something. Dropped while a run is live."""
        return event(self, "chat.submit")

    def on_reset(self) -> Changed:
        """``{}``. Forget the conversation. Dropped while a run is live."""
        return event(self, "chat.reset")
