"""Shipping: one outbound loop, and the subscription it does not have.

    nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_columns)))

Same three-atom composition as Pages. ``Write`` is nu's -- it resolves
the wire path and sends the frame. ``Payload`` is ours and computes what
rides in it. ``next_columns`` blocks until a path is requested, so a lens
nobody is driving costs nothing and never spins.

## Why there is no ``watch`` here

Pages has one: a ``ReactForever`` on ``Space.pages.on_change()`` that
marks its payloads stale, so an edit in one tab paints in every other.
The lens has no equivalent and this is a decision, not an omission.

Three things stand in the way, and none of them is a line of code:

- **no single subscription point.** The lens root is a Shape *class*, and
  a Shape class has no ``on_change`` -- only its slots do. Watching a
  whole space means one ``ReactForever`` per top-level slot, a fan whose
  width is whatever Shape the caller passed, on a surface that advertises
  itself as working over *any* Shape. One slot type without ``on_change``
  and every lens mount breaks.
- **no scoping.** A notification carries the changed key and nothing
  else. The cascade has no key-to-column map, so any write anywhere in
  the space would rebuild every column of every lens tab -- and the
  rebuild is one kv read per prefix of the path. The right version
  prefix-matches the changed key against the path and rebuilds the one
  column it touches. That is design, and it needs the key shape settled
  first.
- **the cursor moves under the reader.** The browser treats a write frame
  as a full replace and keeps per-column focus by index. A live rebuild
  reorders rows under a keyboard cursor that is standing on one.

The hook, when those are answered, is exactly one term composed in beside
this loop: a ``ReactForever`` per watched slot whose body calls
``view.request(path)`` with the path already on screen. ``View`` would
need to remember that path, which is the state it deliberately does not
keep today -- so live updates buy their cursor at the same time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.ui
from nuspace.web.refs.common import Payload


if TYPE_CHECKING:
    from nuspace.web.refs.lens.ref import LensRef
    from nuspace.web.refs.lens.view import View


__all__ = ["columns"]


def columns(ref: LensRef, view: View) -> nu.Nu:
    """Paint the cascade, once per requested path."""
    return nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_columns, label="columns")))
