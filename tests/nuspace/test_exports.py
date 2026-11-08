"""The top level: the everyday names only, op modules as attributes, op terms that travel."""

from __future__ import annotations

import nu
import nuspace
from nu.lang import wire
from nuspace import ops, places


def test_the_top_level_is_the_everyday_list():
    assert sorted(nuspace.__all__) == sorted(
        [
            "Space",
            "State",
            "at",
            "atomic",
            "bracketed",
            "cell",
            "cell_run",
            "errors",
            "here",
            "plane",
            "plane_run",
            "specs",
            "state",
            "worker",
        ]
    )
    assert nuspace.plane is ops.plane
    assert nuspace.state is ops.state
    assert nuspace.at is places.at
    assert nuspace.specs.add_plane is nuspace.specs.ops.add_plane


def test_op_terms_go_over_the_wire_to_a_worker():
    """Built in one process, a term runs in another: every interaction an op uses travels."""
    terms = [
        nuspace.plane.add(key="k"),
        nuspace.plane.remove("p"),
        nuspace.plane.move("p", parent="q"),
        nuspace.cell.add("p", "src"),
        nuspace.cell.set_prog("c", "src"),
        nuspace.plane.title("p"),
        nuspace.plane_run.add("p"),
        nuspace.plane_run.wait("r"),
        nuspace.cell_run.end("cr", "ok"),
        nuspace.worker.add("r", "mp"),
        nuspace.state.clear_cell("c"),
        nuspace.specs.add_plane(nuspace.specs.EMPTY_PLANE),
    ]
    for term in terms:
        assert isinstance(wire.loads(wire.dumps(term)), nu.Nu)
