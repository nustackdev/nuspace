"""A third party extension: an app and a snippet of its own, registered at open.

An :class:`~nuspace.Extension` bundles apps, snippets and env factories. An
installed package ships one through the ``nuspace.extensions`` entry point,
the way nuverse does; a host holding its own passes it straight to
``open_space(extensions=[...])``, which is what this does. Its entries come
ahead of the discovered ones, nuverse's among them.

Headless: the body runs the app, which makes a plane, inserts the snippet as
its one cell, ups the plane on a worker, waits for the countdown, prints it
and returns, which closes the space. The store is a throwaway directory.

Run it::

    python examples/custom.py
"""

from __future__ import annotations

import logging

import nu
import nuspace
import nustd.kv
from nuspace import App, Extension, Snippet, ops
from nuspace.host import space_registry


# Closing the space drops sockets under workers still holding them, and the
# transport logs each one. Expected. At module scope so spawned workers, which
# import this file, are quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


PLANE = "launch"
START = 3

#: The snippet's source: a countdown kept in the cell's own state.
COUNTDOWN = f"""\
import nu
import nustd.kv
import nuspace


class Left(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out():
    step = Left.n.set(nu.ToInt(Left.n) - nu.Int(1))
    return Left.n.set(nu.Int({START})) >> nu.ForRangeDo(0, {START}, nu.DelayedDo(0.1, step))
"""


def launch(plane_id: nu.StrArg | None = None, name: nu.StrArg = "Launch") -> nu.Nu:
    """The ``launch`` app: a plane marked as its own."""
    return ops.add_plane(plane_id, name=name, meta={"made_by": "launch"})


APP = App("launch", "Launches", launch, description="A plane that counts down.")
SNIPPET = Snippet("countdown", "Countdown", COUNTDOWN)
EXTENSION = Extension(apps=(APP,), snippets=(SNIPPET,), name="custom")


def left() -> nu.Nu:
    """The countdown's value, read from the store."""
    return nustd.kv.Snapshot(
        nuspace.Space.planes[PLANE].cells[SNIPPET.name].state.get_item("n", START),
        scope=nuspace.Space,
    )


def body() -> nu.Nu:
    """Run the app, insert the snippet, up the plane, wait for zero, say it."""
    run = nu.Let(
        "example.worker",
        ops.worker(),
        ops.up_plane(PLANE, worker=nu.StrAttrRef("example.worker"), by="example"),
    )
    # Bounded, so a cell that fails does not leave this waiting forever.
    wait = nu.Timeout(10, nu.WhileDo(nu.Gt(nu.ToInt(left()), 0), nu.Delay(0.1)))
    return (
        ops.run_app(APP, plane_id=PLANE)
        >> ops.insert_snippet(PLANE, SNIPPET, cell_id=SNIPPET.name)
        >> run
        >> wait
        >> nu.print(nu.ToStr(left()))
    )


def main() -> None:
    reg = space_registry(extensions=[EXTENSION])
    print(f"apps {sorted(reg.apps)}   snippets {sorted(reg.snippets)}")
    nu.run_in_loop(nuspace.open_space(web=False, extensions=[EXTENSION], body=body()))


if __name__ == "__main__":
    # Load bearing: workers are spawned and re-import __main__. Without the
    # guard, opening a space forks forever.
    main()
