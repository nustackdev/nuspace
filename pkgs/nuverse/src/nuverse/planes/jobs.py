"""The ``jobs`` Plane: headless planes, made, listed and set up from one place.

A job is a plane with ``props.ui`` and ``props.system`` both false: nothing
draws it, and its one cell ``main`` holds its code. The jobs this Plane makes
hang under it, ``made_by`` ``jobs``.

Three cells, meeting in the plane's shared state (``Jobs.selected``):

- ``jobs``: every job, redrawn once a second. A row click selects it.
- ``new``: a name and a button that makes a job, starting as the ``program``
  snippet, and selects it.
- ``job``: the selected job's code, boot switch, restart setting and delete.
  Restart is set on every cell of the job.
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
    props = nuspace.Space.planes[nu.StrAttrRef(key)].props
    headless = nu.And(nu.Not(flag(props.ui)), nu.Not(flag(props.system)))
    return nu.List(nu.Collect(nu.Filter(ops.planes(), headless, key=key)))


def running():
    # Live runs are few: their planes, not every run ever recorded.
    run = nuspace.Space.kernel.runs[nu.StrAttrRef("live")]
    return nu.List(nu.Collect(nu.Unique(nu.Map(ops.live_runs(), nu.ToStr(run.plane), key="live"))))


def restart(pid):
    policy = supervisor.policy_of(pid, "main")
    delay = supervisor.delay_of(pid, "main")
    label = nu.If(
        nu.Eq(policy, "always"),
        nu.Str("always"),
        nu.If(nu.Eq(policy, "on-failure"), nu.Str("on failure"), nu.Str("off")),
    )
    timed = nu.And(nu.Ne(policy, ""), nu.Ge(delay, 0.0))
    return nu.If(timed, label + nu.Str(", ") + nu.Format(delay, "g") + nu.Str("s"), label)


def draw():
    j = nu.StrAttrRef("j")
    name = nuspace.Space.planes[j].name
    booted, live = nu.ListAttrRef("booted"), nu.ListAttrRef("running")
    row = nu.List.of(
        nu.If(name.exists(), nu.ToStr(name), j),
        j,
        nu.If(nu.List(booted).contains(j), "yes", "no"),
        restart(j),
        nu.If(nu.List(live).contains(j), "yes", "no"),
    )
    table = Listing.table.set(
        nu.Dict.of(
            columns=["Name", "ID", "Boot", "Restart", "Running"],
            rows=nu.Collect(nu.Map(nu.Iter(jobs("jobs.draw")), row, key="j")),
        )
    )
    body = nu.Let("booted", init.booted(), nu.Let("running", running(), table))
    return nustd.kv.Snapshot(body, scope=nuspace.Space)


def select():
    click = nu.DictAttrRef("click")
    ids = nu.ListAttrRef("ids")
    at = nu.ToInt(click["row_index"])
    pick = nu.IfDo(nu.Gt(nu.Len(ids), at), Jobs.selected.set(nu.ToStr(nu.List(ids)[at])))
    # The rows are the jobs in creation order: the same read finds the one clicked.
    return nu.IfDo(
        nu.Contains(click, "row_index"),
        nustd.kv.Transaction(nu.Let("ids", jobs("jobs.pick"), pick), scope=nuspace.Space),
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
    here = nu.StrAttrRef(ops.PLANE_ATTR)
    job = nu.StrAttrRef("new.job")
    made = ops.add_plane(name=name, parent=here, ui=False, made_by="jobs")
    fill = ops.add_cell(job, STARTER, cell_id="main", name="main") >> nustd.kv.Transaction(
        Jobs.selected.set(job), scope=nuspace.Space
    )
    return nu.Let("new.job", made, fill)


def out():
    typed = nu.Str(Form.name)
    name = nu.If(nu.Eq(typed, ""), nu.Str("New job"), typed)
    make = nu.Let("new.name", name, create(nu.StrAttrRef("new.name")) >> Form.name.set(""))
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


def snap(term):
    return nustd.kv.Snapshot(term, scope=nuspace.Space)


def draw(job):
    d = View.detail
    name = nuspace.Space.planes[job].name
    policy = supervisor.policy_of(job, "main")
    delay = supervisor.delay_of(job, "main")
    return snap(
        d.title.set(nu.If(name.exists(), nu.ToStr(name), job))
        >> d.editor.set(ops.prog(job, "main"))
        >> d.save.set("Save")
        >> d.boot.set(nu.List(init.booted()).contains(job))
        >> d.restart.policy.choice.set(nu.If(nu.Eq(policy, ""), nu.Str(OFF), policy))
        >> d.restart.delay.set(nu.If(nu.Ge(delay, 0.0), delay, nu.Float(0.0)))
        >> d.delete.set("Delete job", variant="danger")
    )


def restart(job, tag):
    # Plane level: the same policy and delay on every cell of the job.
    choice, delay = nu.StrAttrRef(tag + ".policy"), nu.FloatAttrRef(tag + ".delay")
    cell = nu.StrAttrRef(tag + ".cell")
    each = nu.IfDo(
        nu.Eq(choice, OFF),
        supervisor.unsupervise(job, cell),
        nu.IfDo(
            nu.Gt(delay, 0.0),
            supervisor.supervise(job, cell, choice, delay=delay),
            supervisor.supervise(job, cell, choice),
        ),
    )
    apply = nu.ForEachDo(snap(ops.cells(job)), each, item=tag + ".cell")
    policy = View.detail.restart.policy.choice
    return nu.Let(
        tag + ".policy",
        nu.Str(policy),
        nu.Let(tag + ".delay", nu.ToFloat(View.detail.restart.delay), apply),
    )


def remove(job):
    cell = nu.StrAttrRef("job.gone")
    unsupervised = nu.ForEachDo(
        snap(ops.cells(job)), supervisor.unsupervise(job, cell), item="job.gone"
    )
    # remove_plane asks the job's live runs to stop.
    return (
        unsupervised
        >> init.unboot(job)
        >> ops.remove_plane(job)
        >> nustd.kv.Transaction(Jobs.selected.set(""), scope=nuspace.Space)
    )


def delete(job):
    # Two clicks: the first arms the button, the second deletes.
    button = View.detail.delete
    armed = nu.BoolAttrRef("job.armed")
    click = nu.IfDo(
        armed,
        remove(job),
        nu.SetCmd(armed, nu.Bool(True)) >> button.set("Click again to delete", variant="danger"),
    )
    return nu.Let("job.armed", nu.Bool(False), nu.ReactForever(button.on_click(), click))


def shown(job):
    d = View.detail
    source = nu.StrAttrRef("job.source")
    save = nu.Let("job.source", nu.Str(d.editor), ops.set_prog(job, "main", source))
    boot = nu.IfDo(nu.ToBool(d.boot), init.boot(job), init.unboot(job))
    return (
        View.empty.erase()
        >> draw(job)
        >> nu.ParallelAsync(
            nu.ReactForever(d.save.on_click(), save),
            nu.ReactForever(d.boot.on_change(), boot),
            nu.ReactForever(d.restart.policy.choice.on_change(), restart(job, "job.choice")),
            nu.ReactForever(d.restart.delay.on_change(), restart(job, "job.delay")),
            delete(job),
        )
    )


def hint():
    return View.detail.erase() >> View.empty.hint.set("Select a job")


def out():
    job = nu.StrAttrRef("job.id")
    there = nu.And(nu.Ne(job, ""), snap(ops.plane_exists(job)))
    return follows(Jobs.selected, "job.id", nu.IfDo(there, shown(job), hint()))
"""


PLANE = Plane(
    "jobs",
    "Jobs",
    icon="briefcase",
    description="Headless planes that run code: make them, boot them, restart them.",
    meta={"editable": True, "full_width": False},
    cells=(("jobs", TABLE), ("new", NEW), ("job", DETAIL)),
)
