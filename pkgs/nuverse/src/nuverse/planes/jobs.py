"""The ``jobs`` Plane: headless planes, made, listed and set up from one place.

A job is a plane with ``props.ui`` and ``props.system`` both false: nothing
draws it, and its one cell ``main`` holds its code, its id the job's with
``_main`` after it, so it is unique across the space and never looked up. The jobs this Plane makes
hang under it, ``made_by`` ``jobs``. A headless plane another Plane made is
that Plane's, eg the one a chat talks through, and not a job.

Three cells, meeting in the plane's shared state (``Jobs.selected``):

- ``jobs``: every job, redrawn once a second. A row click selects it.
- ``new``: a name and a button that makes a job, starting as the ``program``
  snippet, and selects it.
- ``job``: the selected job's code, boot switch, restart setting and delete.
  Restart is plane level: the supervisor keeps the job running.
"""

from __future__ import annotations

from nuspace import Plane

from ..snippets import program


__all__ = ["DETAIL", "NEW", "PLANE", "TABLE"]


TABLE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.services import init, supervisor


class Jobs(nuspace.PlaneState):
    selected = nustd.kv.StrRef.slot()


class Listing(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(
        columns=["Name", "ID", "Boot", "Restart", "Running"], clickable_rows=True
    )


def jobs():
    def headless(p):
        props = nuspace.Space.planes[nu.Str(p)].props
        maker = props.made_by.fallback("")
        mine = (maker == "").or_(maker == "jobs")
        return props.ui.fallback(False).not_().and_(props.system.fallback(False).not_()).and_(mine)

    return ops.planes().iter().filter(headless).to_list()


def running():
    # Live runs are few: their planes, not every run ever recorded.
    return nu.List(nu.Collect(nu.Unique(nu.Map(nu.Iter(ops.runs()), lambda run: run["plane"]))))


def restart(pid):
    policy = supervisor.policy_of(pid)
    delay = supervisor.delay_of(pid)
    label = nu.Str(
        nu.Switch(policy, {"always": "always", "on-failure": "on failure"}, default="off")
    )
    timed = (policy != "").and_(delay >= 0.0)
    return nu.If(timed, label + ", " + nu.format(delay, "g") + "s", label)


def table(booted, live):
    def row(at):
        j = nu.Str(at)
        return nu.List.of(
            nuspace.Space.planes[j].name.fallback(j),
            j,
            nu.If(nu.List(booted).contains(j), "yes", "no"),
            restart(j),
            nu.If(nu.List(live).contains(j), "yes", "no"),
        )

    return Listing.table.set(
        nu.Dict.of(
            columns=["Name", "ID", "Boot", "Restart", "Running"],
            rows=jobs().iter().map(row).to_list(),
        )
    )


def draw():
    body = nu.let(
        init.booted(), lambda booted: nu.let(running(), lambda live: table(booted, live))
    )
    return ops.snapshot(body)


def select(click):
    at = nu.int(click["row_index"])

    def pick(ids):
        return nu.IfDo(nu.List(ids).len() > at, Jobs.selected.set(nu.str(nu.List(ids)[at])))

    # The rows are the jobs in creation order: the same read finds the one clicked.
    return nu.IfDo(
        click.contains("row_index"),
        nustd.kv.Transaction(
            nustd.kv.Snapshot(nu.let(jobs(), pick), scope=nuspace.Space),
            scope=nuspace.States,
        ),
    )


def out():
    return draw() >> nu.ParallelAsync(
        nu.ForeverDo(nu.DelayedDo(1.0, draw())),
        nu.ReactForever(Listing.table.on_row_click(), select),
    )
"""


NEW = (
    """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops

#: What a new job's main cell starts as.
STARTER = """
    + repr(program.SNIPPET.source)
    + """


class Jobs(nuspace.PlaneState):
    selected = nustd.kv.StrRef.slot()


def main(job):
    # A job's one cell: its id is the job's with "_main" after it.
    return nu.Str(job) + "_main"


class Form(nustd.ui.Row):
    name = nustd.ui.InputRef.slot(placeholder="Job name")
    create = nustd.ui.ButtonRef.slot(label="Create job")


def create(name):
    # Under the plane running this cell: the Jobs plane.
    here = ops.Here.plane

    def make(made):
        job = nu.Str(made)
        return (
            ops.add_plane(
                backend="mp", name=name, parent=here, ui=False, made_by="jobs", into=made
            )
            >> ops.add_cell(job, STARTER, cell_id=main(job), name="main")
            >> nustd.kv.Transaction(Jobs.selected.set(job), scope=nuspace.States)
        )

    return nu.let("", make)


def out():
    typed = nu.Str(Form.name)
    name = nu.If(typed == "", "New job", typed)
    make = nu.let(name, lambda held: create(nu.Str(held)) >> Form.name.set(""))
    return (
        Form.name.set("")
        >> Form.create.set("Create job")
        >> nu.ReactForever(Form.create.on_click(), make)
    )
"""
)


DETAIL = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.services import init, supervisor
from nuspace.system.utils import follows

OFF = "off"

POLICIES = [
    {"value": OFF, "label": "Off"},
    {"value": supervisor.ON_FAILURE, "label": "On failure"},
    {"value": supervisor.ALWAYS, "label": "Always"},
]


class Jobs(nuspace.PlaneState):
    selected = nustd.kv.StrRef.slot()


def main(job):
    # A job's one cell: its id is the job's with "_main" after it.
    return nu.Str(job) + "_main"


class Policy(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=POLICIES)


class Restart(nustd.ui.Row):
    policy = Policy.slot(label="Restart")
    delay = nustd.ui.NumberInputRef.slot(label="Delay in seconds, 0 backs off", min=0.0)


class Detail(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=3)
    editor = nustd.ui.CodeRef.slot(
        language="python", editable=True, min_height=160, max_height=560
    )
    save = nustd.ui.ButtonRef.slot(label="Save", variant="secondary")
    boot = nustd.ui.SwitchRef.slot(label="Start when the space opens")
    restart = Restart.slot(gap=4, align="end", wrap=True)
    delete = nustd.ui.ButtonRef.slot(label="Delete job", variant="danger")


class Empty(nustd.ui.Column):
    hint = nustd.ui.DividerRef.slot()


class View(nustd.ui.Column):
    empty = Empty.slot()
    detail = Detail.slot(gap=4)


class Asked(nu.Shape):
    # What the restart controls say, read once per change.
    choice = nu.StrRef.slot()
    delay = nu.FloatRef.slot()


def snap(term):
    return ops.snapshot(term)


def draw(job):
    d = View.detail
    policy = supervisor.policy_of(job)
    delay = supervisor.delay_of(job)
    return snap(
        d.title.set(nuspace.Space.planes[job].name.fallback(job))
        >> d.editor.set(ops.prog(main(job)))
        >> d.save.set("Save")
        >> d.boot.set(init.booted().contains(job))
        >> d.restart.policy.choice.set(nu.If(policy == "", OFF, policy))
        >> d.restart.delay.set(nu.If(delay >= 0.0, delay, 0.0))
        >> d.delete.set("Delete job", variant="danger")
    )


def restart(job):
    # Plane level: the supervisor keeps the job running, off stops its run.
    choice, delay = Asked.choice, Asked.delay
    apply = nu.IfDo(
        choice == OFF,
        supervisor.unsupervise(job),
        nu.IfDo(
            delay > 0.0,
            supervisor.supervise(job, choice, delay=delay),
            supervisor.supervise(job, choice),
        ),
    )
    asked = View.detail.restart
    return nu.Frame(
        Asked, apply, choice=nu.Str(asked.policy.choice), delay=nu.float(asked.delay)
    )


def remove(job):
    # remove_plane kills the job's live runs.
    return (
        supervisor.unsupervise(job)
        >> init.unboot(job)
        >> ops.remove_plane(job)
        >> nustd.kv.Transaction(Jobs.selected.set(""), scope=nuspace.States)
    )


def delete(job):
    # Two clicks: the first arms the button, the second deletes.
    button = View.detail.delete

    def clicks(armed):
        click = nu.IfDo(
            nu.Bool(armed),
            remove(job),
            armed.set(True) >> button.set("Click again to delete", variant="danger"),
        )
        return nu.ReactForever(button.on_click(), click)

    return nu.let(False, clicks)


def shown(job):
    d = View.detail
    save = nu.let(nu.Str(d.editor), lambda source: ops.set_prog(main(job), source))
    boot = nu.IfDo(nu.bool(d.boot), init.boot(job), init.unboot(job))
    return (
        View.empty.erase()
        >> draw(job)
        >> nu.ParallelAsync(
            nu.ReactForever(d.save.on_click(), save),
            nu.ReactForever(d.boot.on_change(), boot),
            nu.ReactForever(d.restart.policy.choice.on_change(), restart(job)),
            nu.ReactForever(d.restart.delay.on_change(), restart(job)),
            delete(job),
        )
    )


def hint():
    return View.detail.erase() >> View.empty.hint.set("Select a job")


def showing(job):
    there = (nu.Str(job) != "").and_(snap(ops.plane_exists(job)))
    return nu.IfDo(there, shown(job), hint())


def out():
    return follows(Jobs.selected, showing)
"""


PLANE = Plane(
    "jobs",
    "Jobs",
    icon="briefcase",
    description="Headless planes that run code: make them, boot them, restart them.",
    meta={"editable": True, "full_width": False},
    cells=(("jobs", TABLE), ("new", NEW), ("job", DETAIL)),
    group="System",
    backend="async",
)
