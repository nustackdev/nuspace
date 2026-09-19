"""What a ``+`` makes, per group.

A group is set at birth and says which family a Plane came out of. This is
the other half of that: one entry per group, holding the Planes pressing
``+`` writes and the Cells they are seeded with. Nothing here is read again
afterwards, and nothing in the runtime ever asks a Plane what group it is in.
A group decides what is made; what is made behaves the way its props say,
like any other Plane.

Not :mod:`nuspace.ops.templates`, which is what a new *Cell* starts as. That
one is a seed for one program a person is about to replace; this one is a
whole arrangement, and the two would only share a word.

**A group makes one Plane or two.** Every group has a Plane that draws,
because a row you cannot open is not a row, and it is the one the browser
minted an id for. A group whose thing also *does* something has a second
Plane behind it that runs, and the two name each other in ``cascade_delete``,
so dropping either drops both. That is the model's "a thing that runs and a
thing that draws it are two Planes", and it costs a template rather than any
UI code.

**The Plane that runs takes its id from the Plane that draws.** Derived and
not minted, because a ``+`` has to be a pure function of its event: the only
id an event carries is the browser's, an arm that runs twice has to write one
pair rather than two, and nothing in a tree built once can mint a fresh id
per notification anyway.

**One commit.** The pair and the Cells on it land together, so nothing ever
reads a Plane whose subject is not there yet. That is why the writes come
from :func:`nuspace.ops.plane_writes` and :func:`nuspace.ops.cell_writes`
rather than from the ops that bracket themselves: a Transaction inside a
Transaction opens a second one and commits it on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import nu
from nuspace.ops import templates
from nuspace.ops.cell import cell_writes
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import atomic
from nuspace.shapes import (
    DEFAULT_GROUP,
    EXEC_ASYNC,
    EXEC_MP,
    GROUP_JOB,
    GROUP_PAGE,
    GROUPS,
    TRIGGER_MANUAL,
    TRIGGER_NAV,
    Space,
)


__all__ = [
    "JOB",
    "JOB_CODE",
    "PAGE",
    "RUNS_SUFFIX",
    "CellSeed",
    "Group",
    "PlaneSeed",
    "add",
    "defined",
    "labels",
    "resolve",
]


#: What the id of the Plane that runs is: the drawn Plane's, and this.
RUNS_SUFFIX = "_runs"

#: What :meth:`CellSeed.program` cuts a rendered program at. A byte no python
#: source holds, so the cut lands exactly where the subject's id goes and the
#: text either side is what :meth:`CellSeed.render` would have produced.
_CUT = "\x00"


@dataclass(frozen=True)
class CellSeed:
    """One Cell a Plane is seeded with: what it is called and what it runs.

    The program is a format string over ``{module}`` and ``{root}``, the
    Space's own root shape class, and ``{subject}``, the id of the Plane this
    Cell is about. A subclassed Space is a different set of addresses and a
    program naming :class:`~nuspace.shapes.Space` outright would write to the
    wrong one, which is why the root is rendered in rather than imported.
    """

    cell_id: str
    name: str
    source: str

    def render(self, subject: str, root: type[Space] = Space) -> str:
        """The program, for a subject whose id is known now."""
        return self.source.format(module=root.__module__, root=root.__name__, subject=subject)

    def program(self, subject: nu.StrArg, root: type[Space] = Space) -> nu.Nu:
        """The program, for a subject whose id only the running tree knows.

        The id is baked into the text the Cell stores rather than worked out
        by the program, so what sits in the store afterwards is an ordinary
        program naming an ordinary Plane and nothing has to remember how a
        pair was named. Plane ids never change, so baked in stays true.
        """
        parts = self.render(_CUT, root).split(_CUT)
        written = nu.Str(parts[0])
        for part in parts[1:]:
            written = nu.Add(written, nu.Add(nu.ToStr(subject), nu.Str(part)))
        return written


@dataclass(frozen=True)
class PlaneSeed:
    """One Plane a group makes: how it meets the world, and what is on it."""

    exec_mode: str
    trigger: str
    ui: bool
    editable: bool
    cells: tuple[CellSeed, ...] = ()


@dataclass(frozen=True)
class Group:
    """One group: what a person calls a section of them, and what ``+`` makes."""

    name: str
    #: What the sidebar calls the section this group's Planes are listed in.
    label: str
    #: The Plane that draws. The one the browser minted an id for and routes
    #: to the moment it is made.
    draws: PlaneSeed
    #: The Plane that does the work, where the group has one. It draws
    #: nothing; the Plane above is what shows what it is doing.
    runs: PlaneSeed | None = None


# --- the page ----------------------------------------------------------------

PAGE = Group(
    name=GROUP_PAGE,
    label="Pages",
    # One process for the whole Plane, up while somebody is looking at it,
    # drawn, and authored from inside the Viewer. It starts empty: what a page
    # is for is what a person puts on it.
    draws=PlaneSeed(exec_mode=EXEC_ASYNC, trigger=TRIGGER_NAV, ui=True, editable=True),
)


# --- the job -----------------------------------------------------------------

#: The Cell a job is seeded with, and the one its view opens. Spelled again as
#: a literal inside the template below, because a template is source text and
#: the only name in scope there is its own. ``test_groups`` holds the two
#: together.
JOB_CODE = "c_code"


_JOB_UI = '''import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from {module} import {root}


#: The job this Cell is about. Baked in when the Plane was seeded, which is
#: safe because a plane id never changes.
JOB = "{subject}"

#: The Cell on the job that holds what it does. Seeded with the job, so it is
#: there before anything opens this.
CODE = "c_code"


def table():
    """How the job is set to run, a row per prop, as a write.

    Built fresh at each call site. One node in two tree positions is one
    node, and this one is written on the way in and again on every change.
    """
    return nustd.ui.TableRef("props").set(
        nu.Dict.of(
            columns=nu.List.of("prop", "value"),
            rows=nu.List.of(
                nu.List.of(nu.Str("exec_mode"), ops.plane_exec_mode(JOB, root={root})),
                nu.List.of(nu.Str("trigger"), ops.plane_trigger(JOB, root={root})),
                nu.List.of(nu.Str("ui"), nu.ToStr(ops.plane_ui(JOB, root={root}))),
                nu.List.of(nu.Str("editable"), nu.ToStr(ops.plane_editable(JOB, root={root}))),
            ),
        )
    )


def out(plane, cell):
    """How the job is set to run, and its program in an editor.

    No name anywhere: the sidebar is where a Plane is called something, and
    saying it again at the top of the thing you just clicked is saying it
    twice.

    The editor is seeded from the store on the way in and owns the text from
    then on, so nothing here watches the program it writes: an arm that did
    would set the buffer back under the caret on every save.
    """
    code = nustd.ui.MonacoRef("code")
    prog = {root}.planes[JOB].cells[CODE].prog
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        table()
        >> code.set(prog)
        >> nu.ParallelAsync(
            nu.ReactForever(code.on_change(), prog.set(nu.Str(code))),
            nu.ReactForever({root}.planes[JOB].props.on_change(), table()),
        ),
        scope={root},
    )
'''


JOB = Group(
    name=GROUP_JOB,
    label="Jobs",
    # Drawn, not authored: its Cells are the template's and a person rewriting
    # them is rewriting the view of a job rather than the job.
    draws=PlaneSeed(
        exec_mode=EXEC_ASYNC,
        trigger=TRIGGER_NAV,
        ui=True,
        editable=False,
        cells=(CellSeed(cell_id="c_ui", name="job", source=_JOB_UI),),
    ),
    # A process per Cell, up when somebody says so. It arrives holding the
    # skeleton a Cell starts as, because what the Plane above offers is an
    # editor over it and an editor wants something to open.
    runs=PlaneSeed(
        exec_mode=EXEC_MP,
        trigger=TRIGGER_MANUAL,
        ui=False,
        editable=False,
        cells=(CellSeed(cell_id=JOB_CODE, name="code", source=templates.PROGRAM.source),),
    ),
)


#: Every group, by name. Keyed by :data:`nuspace.shapes.GROUPS`, which is the
#: vocabulary and the order sections are listed in, so a group named there
#: with nothing defined here is a loud failure rather than a missing section.
_DEFINED: dict[str, Group] = {group.name: group for group in (PAGE, JOB)}


def defined() -> tuple[Group, ...]:
    """Every group, in the order the sidebar lists their sections."""
    return tuple(_DEFINED[name] for name in GROUPS)


def labels() -> dict[str, str]:
    """What a person calls each group's section, by group name."""
    return {group.name: group.label for group in defined()}


def resolve(name: object) -> Group:
    """The group called ``name``. Anything else is the default one.

    Total on purpose. Every Plane is in a group and the default is somewhere
    a person writes and reads, so there is no value here to reject and a
    ``+`` that was asked for a word nobody knows still makes something a
    person can open.
    """
    return _DEFINED.get(str(name or ""), _DEFINED[DEFAULT_GROUP])


# --- write -------------------------------------------------------------------


def _seeded(
    seed: PlaneSeed,
    plane_id: nu.StrArg,
    *,
    group: str,
    name: nu.StrArg | None,
    subject: nu.StrArg,
    cascade_delete: list[nu.StrArg] | None,
    root: type[Space],
) -> nu.Nu:
    """One Plane a group makes, and everything on it, as writes."""
    written = plane_writes(
        plane_id=plane_id,
        name=name,
        group=group,
        exec_mode=seed.exec_mode,
        trigger=seed.trigger,
        ui=seed.ui,
        editable=seed.editable,
        cascade_delete=cascade_delete,
        root=root,
    )
    for cell in seed.cells:
        written = written >> cell_writes(
            plane_id,
            cell.program(subject, root=root),
            cell_id=cell.cell_id,
            name=cell.name,
            root=root,
        )
    return written


def _made(
    group: Group,
    plane_id: nu.StrArg,
    name: nu.StrArg | None,
    root: type[Space],
) -> nu.Nu:
    """Everything one group's ``+`` writes, as writes.

    Built fresh per call site: a group is both a case of the switch below and,
    for the default one, the branch nothing matched, and one node in two tree
    positions is one node.
    """
    drawn = _seeded(
        group.draws,
        plane_id,
        group=group.name,
        name=name,
        subject=plane_id,
        cascade_delete=None,
        root=root,
    )
    if group.runs is None:
        return drawn
    runner = nu.Add(nu.ToStr(plane_id), nu.Str(RUNS_SUFFIX))
    # The Plane that runs goes first, so the Plane the browser is about to
    # open never exists without the one it is about. Both name each other, so
    # dropping either drops both.
    return _seeded(
        group.runs,
        runner,
        group=group.name,
        name=name,
        subject=plane_id,
        cascade_delete=[plane_id],
        root=root,
    ) >> _seeded(
        group.draws,
        plane_id,
        group=group.name,
        name=name,
        subject=runner,
        cascade_delete=[runner],
        root=root,
    )


def add(
    group: nu.StrArg,
    *,
    plane_id: nu.StrArg,
    name: nu.StrArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Make whatever ``group`` says a ``+`` makes, in one commit.

    One op and not one per group, so the next group costs an entry in the
    table above and no new wiring. ``group`` is read while the tree runs,
    because a ``+`` arrives as an event carrying which section it was pressed
    under, and every group in the table is a branch of the switch.

    Args:
        group: which family to build. A word nobody knows builds the default
            one rather than nothing, for the reason in :func:`resolve`.
        plane_id: the id of the Plane that draws, which is the one that
            opens. Minted by whoever is asking, so running this twice rewrites
            one arrangement instead of making a second.
        name: what to call it. Every Plane the group makes takes the same
            name: to a person they are one thing.
        root: the Space shape class.
    """
    return atomic(
        nu.SwitchDo(
            nu.ToStr(group),
            {defn.name: _made(defn, plane_id, name, root) for defn in defined()},
            _made(resolve(None), plane_id, name, root),
        ),
        root,
    )
