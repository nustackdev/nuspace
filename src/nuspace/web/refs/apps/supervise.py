"""App supervision: pages' supervisor, with one rule changed.

An app and a section are the same substance, so they get the same
supervisor. ``LocalSupervisor`` already does compile-per-unit, one
asyncio task per unit, per-unit restart, per-unit error isolation and
the fixed status contract. None of that is re-derived here.

What differs is **when** a unit is (re)started, which is the whole
difference between the two pillars:

- A section's supervisor is reconciled once per page open. "Not running"
  means "the page just opened", so ``plan`` starts anything that is not
  already alive.
- An app's supervisor is reconciled continuously, for the life of the
  space. "Not running" is a *terminal* fact -- the app finished, or it
  crashed -- and restarting it on the next reconcile tick would put a
  crashing app into a hot loop and silently resurrect one that returned.

So :class:`AppsSupervisor` narrows the restart trigger to exactly one
thing: the source changed. Everything else about ``plan`` is inherited.
Restarting a stopped or failed app is then an explicit act -- the browser
asks for it, or someone edits the source.

The prefix differs too. A section's is ``sections.<id>`` and it is a ui
mount prefix; an app's is ``apps.<id>`` and it is a kv namespace, because
apps are headless.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.exec.status import SectionSpec
from nuspace.web.refs.pages.supervise import LocalSupervisor


if TYPE_CHECKING:
    from nuspace.web.refs.pages.supervise import _Generation


__all__ = ["AppSpec", "AppsSupervisor"]


class AppSpec(SectionSpec):
    """One app: id + source. ``section_id`` is the app id.

    A plain subclass, not a second dataclass: it adds no fields, it only
    answers ``prefix`` differently.
    """

    @property
    def prefix(self) -> str:
        """The app's own kv namespace. Not a ui mount prefix -- see module doc."""
        return f"apps.{self.section_id}"


class AppsSupervisor(LocalSupervisor):
    """``LocalSupervisor`` whose only restart trigger is a source change."""

    def plan(self, specs: list[SectionSpec]) -> dict[str, _Generation]:
        """Reconcile to ``specs``. New or edited apps start; the rest are left alone.

        Deliberately *not* a super() call with a tweak: the one line that
        differs is the predicate, and inlining the loop keeps the
        difference readable instead of hiding it in a hook.
        """
        wanted = {s.section_id: s for s in specs}

        # Retire apps that vanished from kv. Cancel now, reap in launch().
        for aid in list(self._gens):
            if aid not in wanted:
                self._cancel(self._gens.pop(aid))

        self._pending = []
        for aid, spec in wanted.items():
            existing = self._gens.get(aid)
            # The one difference from pages: state is not consulted. A
            # stopped or failed app stays stopped or failed until its
            # source changes or someone asks for a restart.
            if existing is not None and existing.spec.source == spec.source:
                continue
            if existing is not None:
                self._cancel(existing)
            self._gens[aid] = self._compile(spec)
            if self._gens[aid].status.state != "invalid":
                self._pending.append(aid)
        return dict(self._gens)
