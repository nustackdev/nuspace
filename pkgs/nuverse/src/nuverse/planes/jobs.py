"""The ``jobs`` Plane: headless planes, made, listed and set up from one place.

A job is a plane with ``props.ui`` and ``props.system`` both false: nothing
draws it, and its one cell ``main`` holds its code. The jobs this Plane makes
hang under it, ``made_by`` ``jobs``.

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


def flag(ref):
    return nu.If(ref.exists(), nu.ToBool(ref), nu.Bool(False))


def jobs(key):
    props = nuspace.Space.planes[nu.Str(nu.Attr(key))].props
    headless = nu.And(nu.Not(flag(props.ui)), nu.Not(flag(props.system)))
    return nu.List(nu.Collect(nu.Filter(ops.planes(), headless, key=key)))


def running():
    # Live runs are few: their planes, not every run ever recorded.
    run = nu.Attr("live")
    return nu.List(nu.Collect(nu.Unique(nu.Map(nu.Iter(ops.runs()), run["plane"], key="live"))))


def restart(pid):
    policy = supervisor.policy_of(pid)
    delay = supervisor.delay_of(pid)
    label = nu.If(
        nu.Eq(policy, "always"),
        nu.Str("always"),
        nu.If(nu.Eq(policy, "on-failure"), nu.Str("on failure"), nu.Str("off")),
    )
    timed = nu.And(nu.Ne(policy, ""), nu.Ge(delay, 0.0))
    return nu.If(timed, label + nu.Str(", ") + nu.Format(delay, "g") + nu.Str("s"), label)


def table(booted, live):
    j = nu.Str(nu.Attr("j"))
    name = nuspace.Space.planes[j].name
    row = nu.List.of(
        nu.If(name.exists(), nu.ToStr(name), j),
        j,
        nu.If(nu.List(booted).contains(j), "yes", "no"),
        restart(j),
        nu.If(nu.List(live).contains(j), "yes", "no"),
    )
    return Listing.table.set(
        nu.Dict.of(
            columns=["Name", "ID", "Boot", "Restart", "Running"],
            rows=nu.Collect(nu.Map(nu.Iter(jobs("jobs.draw")), row, key="j")),
        )
    )


def draw():
    body = nu.let(
        init.booted(), lambda booted: nu.let(running(), lambda live: table(booted, live))
    )
    return ops.snapshot(body)


def select():
    click = nu.Attr("click")
    at = nu.ToInt(click["row_index"])

    def pick(ids):
        return nu.IfDo(nu.Gt(nu.Len(ids), at), Jobs.selected.set(nu.ToStr(nu.List(ids)[at])))

    # The rows are the jobs in creation order: the same read finds the one clicked.
    return nu.IfDo(
        nu.Contains(click, "row_index"),
        nustd.kv.Transaction(
            nustd.kv.Snapshot(nu.let(jobs("jobs.pick"), pick), scope=nuspace.Space),
            scope=nuspace.States,
        ),
    )


def out():
    return draw() >> nu.ParallelAsync(
        nu.ForeverDo(nu.DelayedDo(1.0, draw())),
        nu.ReactForever(Listing.table.on_row_click(), select(), changed_key="click"),
    )
"""


NEW = (
    '''\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops

#: What a new job's main cell starts as.
STARTER = """\\
'''
    + program.SOURCE
    + '''"""


class Jobs(nuspace.PlaneState):
    selected = nustd.kv.StrRef.slot()


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
            >> ops.add_cell(job, STARTER, cell_id="main", name="main")
            >> nustd.kv.Transaction(Jobs.selected.set(job), scope=nuspace.States)
        )

    return nu.let("", make)


def out():
    typed = nu.Str(Form.name)
    name = nu.If(nu.Eq(typed, ""), nu.Str("New job"), typed)
    make = nu.let(name, lambda held: create(nu.Str(held)) >> Form.name.set(""))
    return (
        Form.name.set("")
        >> Form.create.set("Create job")
        >> nu.ReactForever(Form.create.on_click(), make)
    )
'''
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


class Policy(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=POLICIES)


class Restart(nustd.ui.Row):
    policy = Policy.slot(label="Restart")
    delay = nustd.ui.NumberInputRef.slot(label="Delay in seconds, 0 backs off", min=0.0)


class Detail(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=3)
    editor = nustd.ui.MonacoRef.slot(language="python", min_height=160)
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
    name = nuspace.Space.planes[job].name
    policy = supervisor.policy_of(job)
    delay = supervisor.delay_of(job)
    return snap(
        d.title.set(nu.If(name.exists(), nu.ToStr(name), job))
        >> d.editor.set(ops.prog(job, "main"))
        >> d.save.set("Save")
        >> d.boot.set(nu.List(init.booted()).contains(job))
        >> d.restart.policy.choice.set(nu.If(nu.Eq(policy, ""), nu.Str(OFF), policy))
        >> d.restart.delay.set(nu.If(nu.Ge(delay, 0.0), delay, nu.Float(0.0)))
        >> d.delete.set("Delete job", variant="danger")
    )


def restart(job):
    # Plane level: the supervisor keeps the job running, off stops its run.
    choice, delay = Asked.choice, Asked.delay
    apply = nu.IfDo(
        nu.Eq(choice, OFF),
        supervisor.unsupervise(job),
        nu.IfDo(
            nu.Gt(delay, 0.0),
            supervisor.supervise(job, choice, delay=delay),
            supervisor.supervise(job, choice),
        ),
    )
    asked = View.detail.restart
    return nu.Frame(
        Asked, apply, choice=nu.Str(asked.policy.choice), delay=nu.ToFloat(asked.delay)
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
            armed.set(nu.Bool(True)) >> button.set("Click again to delete", variant="danger"),
        )
        return nu.ReactForever(button.on_click(), click)

    return nu.let(False, clicks)


def shown(job):
    d = View.detail
    save = nu.let(nu.Str(d.editor), lambda source: ops.set_prog(job, "main", source))
    boot = nu.IfDo(nu.ToBool(d.boot), init.boot(job), init.unboot(job))
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
    there = nu.And(nu.Ne(job, ""), snap(ops.plane_exists(job)))
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
    backend="async",
)
