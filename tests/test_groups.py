"""Every group builds something real, and dropping either half drops both.

A group's Cell programs are text until a Plane made from one is opened, so a
typo in a template is a runtime error inside a generated Plane, on somebody
else's screen. These render every one of them, compile it, construct the tree
its entry point returns and put that tree through the same validation the
runtime would.
"""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops import groups, templates
from nuspace.shapes import GROUPS, Space
from nuspace.space import store


SUBJECT = "p_subject"


def seeds():
    """Every Cell seed every group makes, with the group and Plane it is on."""
    for group in groups.defined():
        for role, seed in (("draws", group.draws), ("runs", group.runs)):
            if seed is None:
                continue
            for cell in seed.cells:
                yield group.name, role, cell


def test_every_group_in_the_vocabulary_is_defined():
    assert tuple(group.name for group in groups.defined()) == GROUPS


def test_every_group_has_a_label():
    assert all(group.label for group in groups.defined())


def test_every_group_draws_something():
    for group in groups.defined():
        assert group.draws.ui, group.name


def test_the_job_view_opens_the_cell_the_job_is_seeded_with():
    """The id is a constant on one side and a literal in source text on the
    other, and an editor over a Cell that is not there opens nothing."""
    assert groups.JOB.runs is not None
    assert [cell.cell_id for cell in groups.JOB.runs.cells] == [groups.JOB_CODE]
    assert f'CODE = "{groups.JOB_CODE}"' in groups.JOB.draws.cells[0].source


@pytest.mark.parametrize(("group", "role", "cell"), list(seeds()), ids=lambda v: str(v))
def test_template_compiles_constructs_and_validates(group, role, cell):
    source = cell.render(SUBJECT)
    # Only a Cell that is about another Plane names one. The skeleton a job's
    # code starts as is about nothing but itself.
    assert SUBJECT in source or "{subject}" not in cell.source
    module: dict = {}
    exec(compile(source, f"<{group}:{role}:{cell.cell_id}>", "exec"), module)  # noqa: S102
    entry = module[templates.ENTRY]
    nu.validate(nu.compile(entry(plane="p_drawn", cell=cell.cell_id)))


@pytest.mark.parametrize(("group", "role", "cell"), list(seeds()), ids=lambda v: str(v))
def test_a_baked_in_subject_is_the_rendered_text(group, role, cell):
    """The runtime form and the literal form are the same program."""
    assert nu.run(cell.program(nu.Str(SUBJECT)))[0] == cell.render(SUBJECT)


# --- what a + writes ---------------------------------------------------------


@pytest.fixture
def space(tmp_path):
    """A Space on disk, and the two calls that write it and read it back."""
    path = str(tmp_path / "space")

    def write(tree):
        nu.run_in_loop(
            nu.With(store(path, root=Space), body=nustd.kv.auto_flow_atomic(tree, scope=Space)),
            nu.Context(),
        )

    def read(tree):
        value, _ = nu.run_in_loop(
            nu.With(store(path, root=Space), body=nustd.kv.Snapshot(tree, scope=Space)),
            nu.Context(),
        )
        return value

    return write, read


def test_a_page_is_one_plane(space):
    write, read = space
    write(ops.groups.add(groups.PAGE.name, plane_id="p_a", name="notes"))
    assert read(ops.plane_ids()) == ["p_a"]
    assert read(ops.plane_group("p_a")) == groups.PAGE.name
    assert read(ops.cell_ids("p_a")) == []


def test_a_job_is_two_planes_naming_each_other(space):
    write, read = space
    write(ops.groups.add(groups.JOB.name, plane_id="p_b", name="crawler"))
    runner = f"p_b{groups.RUNS_SUFFIX}"
    assert sorted(read(ops.plane_ids())) == sorted(["p_b", runner])
    assert read(ops.plane_cascade("p_b")) == [runner]
    assert read(ops.plane_cascade(runner)) == ["p_b"]
    assert read(ops.plane_ui("p_b")) is True
    assert read(ops.plane_ui(runner)) is False
    # Both halves are seeded: the view, and the program the view opens.
    assert read(ops.cell_ids("p_b")) == [groups.JOB.draws.cells[0].cell_id]
    assert read(ops.cell_ids(runner)) == [groups.JOB_CODE]
    assert runner in str(read(ops.prog_of("p_b", groups.JOB.draws.cells[0].cell_id)))


def test_a_group_nobody_knows_builds_the_default_one(space):
    write, read = space
    write(ops.groups.add("nonsense", plane_id="p_c", name="odd"))
    assert read(ops.plane_group("p_c")) == groups.resolve(None).name


def test_the_same_event_twice_writes_one_arrangement(space):
    write, read = space
    for _ in range(2):
        write(ops.groups.add(groups.JOB.name, plane_id="p_d", name="once"))
    assert len(read(ops.plane_ids())) == 2


def test_dropping_either_half_of_a_job_drops_both(space):
    write, read = space
    runner = f"p_e{groups.RUNS_SUFFIX}"
    write(ops.groups.add(groups.JOB.name, plane_id="p_e", name="first"))
    write(ops.remove_plane("p_e"))
    assert read(ops.plane_ids()) == []

    write(ops.groups.add(groups.JOB.name, plane_id="p_e", name="second"))
    write(ops.remove_plane(runner))
    assert read(ops.plane_ids()) == []


def test_the_walk_survives_a_cycle_and_a_dangling_id(space):
    write, read = space
    write(ops.add_plane(plane_id="p_f", cascade_delete=["p_g"]))
    write(ops.add_plane(plane_id="p_g", cascade_delete=["p_f", "p_h"]))
    write(ops.add_plane(plane_id="p_h", cascade_delete=["p_nobody"]))
    write(ops.add_plane(plane_id="p_i"))
    write(ops.remove_plane("p_f"))
    assert read(ops.plane_ids()) == ["p_i"]
