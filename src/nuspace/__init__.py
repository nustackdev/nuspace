"""Nuspace: a space that runs applications over one shape tree, built on Nu.

Rebuild in progress. The imperative driver layer was deleted wholesale
because it was python wearing a Nu costume: Control atoms holding opaque
callables, per-run state on host objects, and a python -> Nu -> arun ->
python cycle instead of one tree.

What nuspace is meant to be is one large Nu program. Storage shapes, the
tpl registry and the wysiwyg template below survived because they are
already that. Everything else gets written against the guides in
``go/progress/tasks/task-144-nuspace-v1/reference/``.
"""

# Order is load-bearing: ``core.shapes`` needs ``App`` from ``apps.shapes`` for
# its slot, so apps must be the first thing imported under this package or an
# entry through ``nuspace.core`` re-enters a half-built ``core.shapes``.
from nuspace.apps import App, run_apps
from nuspace.core import (
    TPL_PROGRAM,
    TPL_TEXT,
    Page,
    Section,
    Space,
    Tpl,
    mint_ordered_id,
    resolve,
)


__version__ = "0.0.0"

__all__ = [
    "TPL_PROGRAM",
    "TPL_TEXT",
    "App",
    "Page",
    "Section",
    "Space",
    "Tpl",
    "mint_ordered_id",
    "resolve",
    "run_apps",
]
