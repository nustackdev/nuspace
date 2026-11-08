"""The brackets: ``nuspace.atomic`` and ``nuspace.bracketed``. Ops carry none, the caller brackets.

- :func:`atomic` is ``nustd.kv.atomic``, re-exported: for code without
  flows. It finds the stores from the refs the term touches and brackets
  only those: a transaction on the one it writes, a snapshot on each it only
  reads, so a key read from Space inside a State write works. A
  read-only term gets snapshots only. Retried on conflict. A term writing
  two stores raises at build: two stores are two commits.
- :func:`bracketed` is for a program written as flows: a bracket around
  each branch of each flow that touches a store, so no bracket is held
  across a wait.

There is no snapshot bracket of its own: ``atomic`` opens one for a term
that only reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.kv
from nuspace.shapes.space import Space
from nuspace.shapes.state import State
from nustd.kv import atomic


if TYPE_CHECKING:
    import nu


__all__ = ["atomic", "bracketed"]


def bracketed(term: nu.Nu) -> nu.Nu:
    """``term`` with a bracket around each branch of each flow that touches Space or State.

    ``nustd.kv.auto_flow_atomic``, one pass per store: a snapshot around a
    branch that only reads, a transaction around one that writes, nothing
    around one that touches no store. Each branch of a flow is bracketed on
    its own, so a loop, a wait or a subscription gets a bracket per step.
    Brackets already in the term are kept and looked into, never doubled.

    Known edges, as ``auto_flow_atomic`` has them: an op is itself a flow
    (its checks and writes in a ``>>``, a minting one inside a ``let``), so
    each of its steps gets its own bracket and its writes land in several
    commits, not one. A wrapper that is not a flow (``Frame``, ``let``,
    ``TryCatch``, ``Timeout``) and reads a store outside its flow branches
    gets one bracket around all of it, held for as long as it runs; a subscription keyed by a dynamic read is
    bracketed whole. Code shaped like that brackets by hand with
    :func:`atomic`. Stores other than Space and State (a device's) are left
    to their own code.

    Never raises.
    """
    return nustd.kv.auto_flow_atomic(nustd.kv.auto_flow_atomic(term, scope=Space), scope=State)
