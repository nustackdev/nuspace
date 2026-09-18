"""What a new Cell starts as.

A Cell holds a Nu program and there is no second substance, so a template is
not a kind and nothing branches on which one made a Cell. It is a seed, and
the store keeps only what came out of it.

Two of them, and the difference is who writes the program:

``program``
    The person does. The template is a skeleton they replace, so passing
    content replaces it outright.

``ticker``
    The template does. The program is the same for every Cell made from it
    and there is nothing to type, so content is not offered.

A template renders against the Space's own root shape class, because a
subclassed Space is a different set of addresses and a program that named
:class:`~nuspace.shapes.Space` outright would write to the wrong one.

The rendered program is a python module, not an expression, and its entry
point's signature is how it asks for what it runs under. nuspace offers two
names, ``plane`` and ``cell``, so ``def out(plane, cell)`` gets both and
``def out()`` gets neither. Seeding the skeleton with the full signature is
how that stays discoverable without reading this file.

There is no migration. Changing a template changes what a Cell made from it
would start as, and Cells already in the store keep the program they hold.
"""

from __future__ import annotations

from dataclasses import dataclass

from nuspace.shapes import Space


__all__ = [
    "DEFAULT_TEMPLATE",
    "ENTRY",
    "SCOPE",
    "SCOPE_CELL",
    "SCOPE_PLANE",
    "TEMPLATES",
    "TEMPLATE_PROGRAM",
    "TEMPLATE_TICKER",
    "Template",
    "names",
    "resolve",
    "scope",
    "source",
]


#: The function nuspace calls to get a Cell's tree.
ENTRY = "out"

#: The id of the Plane the Cell is on.
SCOPE_PLANE = "plane"

#: The Cell's own id, unique in its Plane.
SCOPE_CELL = "cell"

#: Every name a Cell's entry point may ask for, and nothing else is offered.
SCOPE = (SCOPE_PLANE, SCOPE_CELL)

TEMPLATE_PROGRAM = "program"
TEMPLATE_TICKER = "ticker"

#: A Cell nobody said anything about is one somebody is about to write.
DEFAULT_TEMPLATE = TEMPLATE_PROGRAM


_PROGRAM = '''import nu
import nustd.kv
from {module} import {root}


# `out` may ask for `plane` and `cell`, the ids this program runs under.
def out(plane, cell):
    """Put one key in this Cell's own state, then end."""
    # A Cell's state is at the Cell's own path, so nothing here spells out
    # where it lives beyond the two ids it was handed.
    state = {root}.planes[plane].cells[cell].state
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(state.set_item("hello", nu.Str("world")), scope={root})
'''


_TICKER = '''import nu
import nustd.kv
from {module} import {root}


def out(plane, cell):
    """Count up in this Cell's own state, one step a second, until cancelled."""
    state = {root}.planes[plane].cells[cell].state
    now = nu.Int(nu.ToInt(state.get_item("ticks", nu.Int(0))))
    step = state.set_item("ticks", now + nu.Int(1))
    return nustd.kv.auto_flow_atomic(nu.ForeverDo(nu.DelayedDo(nu.Float(1.0), step)), scope={root})
'''


@dataclass(frozen=True)
class Template:
    """One seed: the program it produces and whether content replaces it."""

    name: str
    #: A format string over ``{module}`` and ``{root}``, the space's own root
    #: shape class.
    source: str
    #: Whether the person writes the program. When they do, the source above
    #: is only what they start from.
    arbitrary: bool = False

    def render(self, root: type[Space] = Space, content: str = "") -> str:
        """The program a Cell made from this template stores.

        Args:
            root: the Space shape class the program addresses.
            content: what the person wrote. Used only by a template they
                write themselves, and only when there is something in it.
        """
        if self.arbitrary and content:
            return content
        return self.source.format(module=root.__module__, root=root.__name__)


PROGRAM = Template(name=TEMPLATE_PROGRAM, source=_PROGRAM, arbitrary=True)

TICKER = Template(name=TEMPLATE_TICKER, source=_TICKER)

TEMPLATES: dict[str, Template] = {t.name: t for t in (PROGRAM, TICKER)}


def names() -> tuple[str, ...]:
    """Every template a Cell can be made from."""
    return tuple(TEMPLATES)


def resolve(name: object) -> Template:
    """The template called ``name``. Anything else is a plain program.

    Total on purpose. Every Cell is a program, so there is no value here to
    reject and nothing downstream has a failure case to carry.
    """
    return TEMPLATES.get(str(name or ""), PROGRAM)


def source(name: object, *, root: type[Space] = Space, content: str = "") -> str:
    """The program a new Cell made from ``name`` starts as."""
    return resolve(name).render(root, content)


def scope(plane: object, cell: object) -> dict[str, object]:
    """What a Cell's entry point is offered, by parameter name.

    The values are whatever the caller has: literals from a CLI, or terms a
    fold binds per arm. Only the names a program declares are passed to it.
    """
    return {SCOPE_PLANE: plane, SCOPE_CELL: cell}
