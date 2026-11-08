"""The core ops: nus over the stores, one module per shape, re-exported at the top.

``ops/plane.py`` is ``nuspace.plane``, ``ops/cell.py`` is ``nuspace.cell``,
and so on, mirroring :mod:`nuspace.shapes` file for file. Programs write the
module in front, ``nuspace.plane.add(...)``, never ``from ... import add``.

- **Bare terms.** An op carries no bracket. The caller brackets it:
  ``nuspace.atomic(...)`` in code without flows (one commit on the store it
  writes, a snapshot on each it only reads), ``nuspace.bracketed`` in flows.
  What decides a write is read in the same term, so under ``atomic`` it
  lands in the same commit. An op is itself a flow of checks and writes,
  so ``bracketed`` brackets each of its steps on its own (see
  :func:`~nuspace.ops.brackets.bracketed`). Something that needs two stores
  is two ops in a row, two commits.
- **Declarative.** Ops touch only the stores. They write what is wanted
  (``plane_run.add`` starts nothing, it adds a record) and what drivers
  observed (``cell_run.end``); the kernel and the other drivers make
  reality match.
- **Raise, never fail silently.** An op that cannot do what it says raises
  one of :mod:`nuspace.errors` and the commit aborts. A no-op only where it
  harms nothing and races are normal, eg stopping a run that already ended.
- **Constant keys.** Each op touches a constant number of keys, except the
  inherent cases its doc names (removing a subtree). Nothing iterates
  planes, cells or runs: ops read indexes.
- **Ids.** The id acted on comes first. Minting ops mint when they evaluate
  and set ``into=`` in the same commit.
"""

from . import cell, cell_run, plane, plane_run, state, worker


__all__ = ["cell", "cell_run", "plane", "plane_run", "state", "worker"]
