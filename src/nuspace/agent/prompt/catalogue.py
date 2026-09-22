"""The vocabulary section, generated from nu.inspect rather than written.

Hand-written vocabulary rots, and a stale line in a prompt is worse than no
line: the model treats it as authoritative and follows a wrong arity off a
cliff. This reads the same records the docs site reads, so a rename in the
core is a rename in the next prompt.

Scope is nucore, the Nu language itself. The nustd fabric surfaces
(``nustd.mem``, ``nustd.kv``, ``nustd.ui``, ...) are deliberately absent: which of
them an agent can reach is decided by the caller's bindings, not by us, and
front-loading all of them would spend thousands of tokens on Refs the model
cannot resolve. ``Inspect`` is how it finds them, and ``inspect.md`` teaches
that. A caller who has bound a fabric adds it to ``modules``.

Nothing is dropped quietly. The one documented cost centre - the 38
``Bytes*`` string methods in ``nu.forms.primitives`` - is left in by
default, because two models have already burned a whole turn budget on an
atom a prompt did not mention and a silent omission is exactly that failure.
``omit`` exists for a caller who wants them gone, and when it fires the
rendered catalogue says so on its own line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu.context
import nu.core
import nu.core.flows
import nu.core.spans
import nu.forms.collections
import nu.forms.primitives
import nu.inspect
import nu.lang
import nu.prog
from nu.inspect import catalogue_forms, catalogue_interactions, catalogue_refs
from nuspace.agent.prompt.sections import Section


if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


__all__ = [
    "DEFAULT_MODULES",
    "bytes_methods",
    "catalogue_section",
    "render_catalogue",
]


#: The nucore modules an agent composes against. Verified pairwise disjoint
#: apart from ``Hex``, which ``nu.core`` and ``nu.forms.primitives`` both
#: export. ``nu.core.reactive`` is absent because ``nu.core`` re-exports all
#: five of its atoms; ``nu.domains.shape`` is absent because it holds the
#: abstract Ref bases a fabric specialises, not anything a model writes.
DEFAULT_MODULES: tuple[ModuleType, ...] = (
    nu.core,  # the atom bulk: arithmetic, comparison, iteration, casts
    nu.core.flows,  # the *Do mutators, including ForEachDo / ForRangeDo
    nu.core.spans,  # transparent wrappers: Retry, TryCatch, Transaction
    nu.context,  # AttrRef and friends - how a loop body names its element
    nu.lang,  # Literal, plus the kind taxonomy the thesis section names
    nu.forms.primitives,  # Int / Str / Bool forms and their method atoms
    nu.forms.collections,  # List / Dict / Set / Tuple forms
    nu.prog,  # Eval / LoadNu / Program - the carrier the host runs
    nu.inspect,  # Inspect itself, so it appears where the model looks
)


def bytes_methods(name: str) -> bool:
    """True for the ``Bytes*`` string-method atoms. Pass as ``omit`` to drop them."""
    return name.startswith("Bytes")


def catalogue_section(
    modules: tuple[ModuleType, ...] = DEFAULT_MODULES,
    *,
    omit: Callable[[str], bool] | None = None,
) -> Section:
    """The catalogue as a prompt section.

    Args:
        modules: the modules whose subjects become the vocabulary. Add a
            fabric module here when the caller has bound one.
        omit: a predicate over subject names. Anything it accepts is left out
            and announced in the rendered text.

    Returns:
        A Section named ``catalogue``.
    """
    return Section("catalogue", lambda: render_catalogue(modules, omit=omit))


def render_catalogue(
    modules: tuple[ModuleType, ...] = DEFAULT_MODULES,
    *,
    omit: Callable[[str], bool] | None = None,
) -> str:
    """One header, then one ``name  summary`` line per subject per module."""
    lines = [
        "# Catalogue",
        "",
        "Every subject you can compose against, one line each. For args, notes and",
        'examples, compose `nu.inspect.Inspect("<dotted.path>")` and return it.',
    ]
    for module in modules:
        lines.append("")
        lines.append(_module_lines(module, omit))
    return "\n".join(lines)


def _module_lines(module: ModuleType, omit: Callable[[str], bool] | None) -> str:
    lines = [f"## {module.__name__}"]
    groups = (
        ("forms", catalogue_forms(module)),
        ("refs", catalogue_refs(module)),
        ("interactions", catalogue_interactions(module)),
    )
    for group_name, group in groups:
        kept = [record for record in group if omit is None or not omit(record.name)]
        dropped = len(group) - len(kept)
        if not kept and not dropped:
            continue
        lines.append(f"  {group_name}:")
        for record in kept:
            summary = (record.summary or "-").rstrip(".")
            lines.append(f"    {record.name:<22} {summary}")
        if dropped:
            lines.append(
                f"    ({dropped} more omitted from this list; "
                f'`nu.inspect.Inspect("{module.__name__}")` shows all of them)'
            )
    return "\n".join(lines)
