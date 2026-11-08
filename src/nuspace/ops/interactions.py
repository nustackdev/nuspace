"""The nu interactions the ops need of their own. Ops are composed of these and kv refs.

- :class:`Fabrics`: the fabrics a prog uses, worked out from its built term.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
import nu.tree
from nu.lang import ScalarQuery
from nustd.ui.core import Ref as UiRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["UI", "Fabrics"]


#: The ui fabric's name in ``Cell.fabrics``.
UI = "ui"

# In process: the host's own interpreter builds the term it inspects.
_BRACE = nu.prog.PyBrace()


def _found(built: object) -> list[str]:
    """The fabrics a built term uses. Today only ui is told apart. A failed build uses none."""
    if not isinstance(built, nu.Nu):
        return []
    drawn = nu.tree.find_first(built, lambda node: isinstance(node, UiRef)) is not None
    return [UI] if drawn else []


class Fabrics(ScalarQuery):
    """The fabrics ``prog`` uses: its term built, then read. Pure analysis, no store.

    Building runs the prog's module code in this process, offered the
    ``plane`` and ``cell`` a cell run offers it. Source that does not build
    uses nothing, as it stands. Only ``"ui"`` is detected for now.

    Args:
        prog: The source.
        plane: The plane id offered to the build.
        cell: The cell id offered to the build.

    Yields:
        A list of fabric names, eg ``["ui"]``.
    """

    def __init__(self, prog: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg) -> None:
        super().__init__(prog, plane, cell)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        def thunk(rt: Runtime) -> object:
            scope = {"plane": plane(rt), "cell": cell(rt)}
            return _found(_BRACE.construct(str(prog(rt)), scope=scope))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        async def athunk(rt: Runtime) -> object:
            scope = {"plane": await plane(rt), "cell": await cell(rt)}
            return _found(await _BRACE.aconstruct(str(await prog(rt)), scope=scope))

        return athunk
