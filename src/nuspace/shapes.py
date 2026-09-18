"""The store layout: Space, Plane, Cell, and their props.

Layer zero. It imports ``nu`` and ``nustd.kv`` and nothing of nuspace, so
everything else reads it and it reads nothing back.

What the store holds::

    Space
      planes
        <plane>
          name
          props    exec_mode, trigger, ui, editable
          cells
            <cell>
              name
              props  restart, reload
              prog
              state
              error
          order

One container of Planes and one container of Cells inside each. There is no
third noun and no container named after a kind.

``props`` is its own node so a subscription can name it. A Plane's Cells live
inside the Plane, so a depth unbounded watch on ``planes[p]`` fires on every
keystroke in every Cell it holds, while a watch on ``planes[p].props`` fires
when somebody changes how the Plane runs and at no other time. One level
down, a reloading Cell watches ``cells[c].prog``, so the writes its own
program makes to ``state`` never restart it.

``name`` sits beside ``props`` for the same reason: renaming a thing is not a
change to how it runs.

``Space`` is also the store's tag. kv refs resolve their Navigator by root
shape class, so the bracket in :mod:`nuspace.space` binds the stack under
this class, and a subclassed Space is a different set of addresses.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = [
    "DEFAULT_EDITABLE",
    "DEFAULT_EXEC_MODE",
    "DEFAULT_RELOAD",
    "DEFAULT_RESTART",
    "DEFAULT_TRIGGER",
    "DEFAULT_UI",
    "EXEC_ASYNC",
    "EXEC_MODES",
    "EXEC_MP",
    "RESTARTS",
    "RESTART_ALWAYS",
    "RESTART_NO",
    "RESTART_ON_FAILURE",
    "TRIGGERS",
    "TRIGGER_BOOT",
    "TRIGGER_MANUAL",
    "TRIGGER_NAV",
    "Cell",
    "CellProps",
    "Plane",
    "PlaneProps",
    "Space",
]


#: The whole Plane in one process, its Cells as asyncio tasks in it.
EXEC_ASYNC = "async"

#: One process per Cell.
EXEC_MP = "mp"

#: Both offload. They differ in granularity, not in whether they leave main.
EXEC_MODES = (EXEC_ASYNC, EXEC_MP)

#: Up as soon as the Space is open.
TRIGGER_BOOT = "boot"

#: Up when somebody says so.
TRIGGER_MANUAL = "manual"

#: Up per browser connection that navigates to it, down when it leaves.
TRIGGER_NAV = "nav"

TRIGGERS = (TRIGGER_BOOT, TRIGGER_MANUAL, TRIGGER_NAV)

#: A program that ends stays ended.
RESTART_NO = "no"

#: A program that raises is started again. A clean end stays ended.
RESTART_ON_FAILURE = "on-failure"

#: A program that ends is started again, either way.
RESTART_ALWAYS = "always"

RESTARTS = (RESTART_NO, RESTART_ON_FAILURE, RESTART_ALWAYS)

#: One process for the Plane is the cheaper arrangement, so it is the one a
#: Plane gets when nobody says otherwise.
DEFAULT_EXEC_MODE = EXEC_ASYNC

#: Nothing starts itself. A Plane that should be up at boot says so.
DEFAULT_TRIGGER = TRIGGER_MANUAL

#: A Plane draws nothing until somebody says it does.
DEFAULT_UI = False

#: Authoring is the exception, so a Plane is read-only until somebody says
#: otherwise.
DEFAULT_EDITABLE = False

DEFAULT_RESTART = RESTART_NO

DEFAULT_RELOAD = True


class CellProps(nu.Shape):
    """A Cell's own lifecycle. Its siblings can differ.

    ``restart`` is about the program ending and ``reload`` is about the
    program changing, which is why they are two axes: a Cell can come back
    after every exit and still ignore edits, or the other way round.
    """

    restart = nustd.kv.StrRef.slot()
    reload = nustd.kv.BoolRef.slot()


class Cell(nu.Shape):
    """A Nu program, and the only thing in a Space that executes.

    ``prog`` is a python module whose entry point returns a Nu tree. nuspace
    hands it the ids of the Plane and the Cell it is, and roots the refs it
    names under this Cell, so a program never spells out where it lives.

    ``state`` and ``error`` are two slots because the writers differ.
    ``state`` is the program's own and holds whatever it likes under whatever
    keys; ``error`` is nuspace's and is the failure a browser reads, so a
    program cannot clobber a status by naming a key. Both sit at this Cell's
    path, which is why a Cell id has to be unique in its Plane and nothing
    wider.
    """

    name = nustd.kv.StrRef.slot()
    props = nustd.kv.ShapeRef.slot(CellProps)
    prog = nustd.kv.ProgramRef.slot()
    state = nustd.kv.DictRef.slot(object)
    error = nustd.kv.StrRef.slot()


class PlaneProps(nu.Shape):
    """How a Plane meets the world: where its Cells run, when, and how drawn.

    ``exec_mode`` and ``trigger`` are execution, ``ui`` and ``editable`` are
    presentation. They sit together because a change to any of them rearranges
    the Plane, and they stay four slots because the runtime reads the first
    two and the browser reads the other two.

    ``ui`` says the Plane draws, and it is what the sidebar filters on.

    ``editable`` says a person can author this Plane's own Cells from inside
    the Viewer: add one, drag one, rewrite one. It is not about whether the UI
    contains an editor. A generated Plane holding a monaco Cell is
    ``editable: false``, because what it offers is what its program does.
    """

    exec_mode = nustd.kv.StrRef.slot()
    trigger = nustd.kv.StrRef.slot()
    ui = nustd.kv.BoolRef.slot()
    editable = nustd.kv.BoolRef.slot()


class Plane(nu.Shape):
    """A collection of Cells, and how and when they run and how they look.

    Arrangement only. Nothing evaluates a Plane, so running one means
    starting its Cells the way its props say.

    A Cell tiles a Plane, so the Cells have a sequence and ``order`` is it:
    list position is the position, with no index to renormalise and no
    gap to leave. It sits beside ``cells`` rather than inside a Cell so
    rearranging the tiling is one write that touches no Cell, which is why
    a drag wakes no arm. The runtime reads the keys of ``cells`` and never
    this list, so a Cell that reached the store some other way still runs;
    it is only drawn last.
    """

    name = nustd.kv.StrRef.slot()
    props = nustd.kv.ShapeRef.slot(PlaneProps)
    cells = nustd.kv.ShapesDictRef.slot(Cell)
    order = nustd.kv.ListRef.slot(str)


class Space(nu.Shape):
    """The world. One flat container of Planes, keyed by id.

    Flat so a Plane is one lookup away at a fixed depth and a route or a CLI
    argument addresses it directly. Planes holding Planes is a relation
    between two Planes, so it belongs in fields that name each other rather
    than in storage depth.
    """

    planes = nustd.kv.ShapesDictRef.slot(Plane)
