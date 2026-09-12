"""How a nuspace driver builds one arm, and how it reads one event.

A driver is a flat ``|`` of arms and nothing else. An arm is one subscription
reacting forever, and everything that makes that survivable is here rather
than in either driver, so the two cannot drift apart on it.

Three details, all load-bearing:

- **Per-arm attrs namespaces.** ``Parallel`` children share one runtime and
  therefore one ``ctx.attrs``, so an arm names its bindings after itself. Two
  arms binding ``e`` would read each other's events the moment one awaited.
- **A fresh subscription per arm.** Never a shared ``Changed`` term: two arms
  holding one node share one handle, and the first to end closes it under the
  other.
- **The double guard.** The inner ``TryCatch`` keeps the loop alive across a
  bad frame; the outer one means a dead arm merely completes instead of
  propagating and dropping the websocket. Both print -- degrading is allowed
  here, degrading in silence is not.
"""

from __future__ import annotations

import nu
from nu.core.io import STDOUT


__all__ = ["Arms", "field_ids", "field_index", "field_str"]


class Arms:
    """Arm factory for one driver. Holds the label its failures print under."""

    __slots__ = ("label",)

    def __init__(self, label: str) -> None:
        self.label = label

    def report(self, what: str) -> nu.Nu:
        """Say something went wrong, on the server's stdout. The loop carries on."""
        return nu.Print(
            STDOUT,
            nu.Str(f"nuspace {self.label} driver: {what}: "),
            nu.ToStr(nu.AttrRef("error")),
        )

    def guard(self, term: nu.Nu, what: str) -> nu.Nu:
        """Run ``term``, and survive it raising."""
        return nu.TryCatch(term, catch=self.report(what))

    def event(self, name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
        """One subscription, forever, twice guarded.

        Args:
            name: this arm's attrs namespace, and what a failure is reported
                as. Unique per arm: parallel arms share one ``ctx.attrs``.
            change: the subscription to react to. Freshly built, never shared.
            body: what to run per notification, already written against
                ``nu.DictAttrRef(name)`` where it needs the event.
        """
        return self.guard(nu.ReactForever(change, self.guard(body, name), changed_key=name), name)

    def state(self, name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
        """One kv subscription, forever, reshipping whatever the store says now.

        No ``changed_key``: a state arm reads the store, never the key that
        woke it, so which write in a burst it is looking at makes no
        difference to what it ships.

        A kv subscription is depth-unbounded, so one delete wakes this a dozen
        times and the browser is handed a dozen identical answers. Wasteful,
        not wrong -- every frame carries the whole current answer, so the last
        one is the true one and the ones before it were true when they were
        sent. ``nu.Debounce`` is the obvious collapse and does not fit: it
        parks an ``asyncio.Task`` in ``ctx.attrs``, and the ``ctx.lazy`` inside
        ``auto_flow_atomic`` deep-copies attrs, which a Task cannot survive.
        """
        return self.guard(nu.ReactForever(change, self.guard(body, name)), name)


# --- reading one event's fields --------------------------------------------
#
# Total on purpose. A field the browser left out reads as its default rather
# than as EMPTY, so an op is handed a string where it wants a string and
# no-ops on a missing row instead of dying inside a codec.


def field_str(name: str, field: str) -> nu.Nu:
    """One string field off the arm's event. ``""`` when absent."""
    return nu.ToStr(nu.DictAttrRef(name).get_item(nu.Str(field), nu.Str("")))


def field_ids(name: str, field: str) -> nu.Nu:
    """One list-of-ids field off the arm's event. Empty when absent."""
    return nu.List(nu.DictAttrRef(name).get_item(nu.Str(field), nu.List.of()))


def field_index(name: str, field: str, length: nu.Nu) -> nu.Nu:
    """One position field off the arm's event, defaulting to one past the end.

    Zero is a real position, so the usual ``0`` default would silently
    prepend everything a caller forgot to place.
    """
    return nu.ToInt(nu.DictAttrRef(name).get_item(nu.Str(field), length))
