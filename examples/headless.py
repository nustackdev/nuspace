"""A Space of two Planes and three Cells, run headless, start to finish in twelve seconds.

Everything phase 1 claims, shown rather than described:

- a Plane whose ``exec_mode`` is ``async`` holds two Cells in one worker;
- a Plane whose ``exec_mode`` is ``mp`` gives its one Cell a process to itself;
- nothing a person wrote runs in the main process, which the pids prove;
- ``restart: always`` brings a program back after it returns, ``restart: no``
  leaves it stopped;
- ``reload`` restarts the Cell whose program changed, and only that one.

Every Cell runs the same tiny program: count this run, stamp the process it ran
in, say which version of itself it is. Three numbers, and between them they
answer every question above.

Run it::

    python examples/headless.py

The Space is left on disk, so ``nuspace -s <path> ls`` reads what it did.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

import nu
import nustd.kv
from nuspace import (
    EXEC_ASYNC,
    EXEC_MP,
    RESTART_ALWAYS,
    RESTART_NO,
    TRIGGER_BOOT,
    Space,
    open_space,
    ops,
    store,
)
from nuspace.drivers import run_space


# Closing the Space drops two sockets under workers that are still holding them,
# and the transport logs every one of those as an error. Expected, and the only
# thing this demo has to say is what it printed itself. At module scope so a
# spawned worker, which imports this file, is quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


LOOP, BEAT, HOLD = "loop", "beat", "hold"
SOLO, WORK = "solo", "work"

#: How long the Space runs before the first report. Long enough for a Cell that
#: keeps coming back to have come back a good few times.
BOOT_SECONDS = 5.0

#: How long an edit is given to land before the report after it.
EDIT_SECONDS = 3.0


def source(version: int) -> str:
    """The program every Cell holds. Counts the run, stamps the process, ends.

    Ending is the point: a program that returns is what ``restart`` is about,
    so the same three lines demonstrate both settings of it.
    """
    return f'''import os

import nu
import nustd.kv
from nuspace import Space


def out(plane, cell):
    """Count this run, stamp the process it ran in, and end."""
    state = Space.planes[plane].cells[cell].state
    runs = nu.Int(nu.ToInt(state.get_item("runs", nu.Int(0))))
    return nustd.kv.auto_flow_atomic(
        state.set_item("runs", runs + nu.Int(1))
        >> state.set_item("pid", nu.Int(os.getpid()))
        >> state.set_item("version", nu.Int({version})),
        scope=Space,
    )
'''


# --- what the Space is -------------------------------------------------------


def seed():
    """Two Planes and three Cells, each Cell one commit."""
    return (
        ops.add_plane(plane_id=LOOP, exec_mode=EXEC_ASYNC, trigger=TRIGGER_BOOT)
        >> ops.add_cell(LOOP, source(1), cell_id=BEAT, restart=RESTART_ALWAYS)
        >> ops.add_cell(LOOP, source(1), cell_id=HOLD, restart=RESTART_NO)
        >> ops.add_plane(plane_id=SOLO, exec_mode=EXEC_MP, trigger=TRIGGER_BOOT)
        >> ops.add_cell(SOLO, source(1), cell_id=WORK, restart=RESTART_ALWAYS)
    )


# --- what it says while it runs ----------------------------------------------


def say(text):
    return nu.Print(nu.STDOUT, nu.Str(text), flush=True)


def kept(plane, cell, key):
    """One number a Cell's program kept, zero where it has not written it yet."""
    state = Space.planes[plane].cells[cell].state
    return nu.Int(nu.ToInt(state.get_item(key, nu.Int(0))))


def show(plane, cell):
    return nu.Print(
        nu.STDOUT,
        nu.Str(f"  {plane}/{cell:<6}"),
        nu.Str("  runs "),
        nu.ToStr(kept(plane, cell, "runs")),
        nu.Str("   version "),
        nu.ToStr(kept(plane, cell, "version")),
        nu.Str("   pid "),
        nu.ToStr(kept(plane, cell, "pid")),
        sep="",
        flush=True,
    )


def report(title):
    return say(title) >> show(LOOP, BEAT) >> show(LOOP, HOLD) >> show(SOLO, WORK)


def timeline():
    """The whole demo as one branch: watch, edit, watch, edit, watch.

    It runs beside the runtime in the main process. When it ends, the Race
    around it ends, which is what closes the Space.
    """
    return (
        nu.DelayedDo(
            nu.Float(BOOT_SECONDS),
            report(f"\nact 1  {BOOT_SECONDS:.0f} seconds in, nobody has touched anything"),
        )
        >> say("\nact 2  editing loop/beat to version 2")
        >> ops.set_prog(LOOP, BEAT, source(2))
        >> nu.DelayedDo(
            nu.Float(EDIT_SECONDS),
            report("       beat is on the new program, hold has not moved"),
        )
        >> say("\nact 3  editing loop/hold, which has been stopped since its one run")
        >> ops.set_prog(LOOP, HOLD, source(2))
        >> nu.DelayedDo(
            nu.Float(EDIT_SECONDS),
            report("       the edit started it again, for exactly one more run"),
        )
    )


def body():
    """Seed the Space, then run it against the timeline until the timeline ends."""
    return nustd.kv.auto_flow_atomic(seed(), scope=Space) >> nu.Race(
        run_space(),
        nustd.kv.auto_flow_atomic(timeline(), scope=Space),
    )


# --- what it says afterwards -------------------------------------------------


def read_back(path):
    """What the three Cells kept, read out of the closed store."""
    value, _ = nu.run_in_loop(
        nu.With(
            store(path),
            body=nustd.kv.Snapshot(
                nu.Dict.of(
                    beat=ops.cell_state(LOOP, BEAT),
                    hold=ops.cell_state(LOOP, HOLD),
                    work=ops.cell_state(SOLO, WORK),
                ),
                scope=Space,
            ),
        ),
        nu.Context(),
    )
    return value


def verdict(path, main_pid):
    """Every claim as a check against the final state, so it passes or it does not."""
    state = read_back(path)
    runs = {k: state[k].get("runs", 0) for k in state}
    pids = {k: state[k].get("pid", 0) for k in state}
    version = {k: state[k].get("version", 0) for k in state}
    checks = [
        (
            "restart always",
            runs["beat"] >= 5,
            f"loop/beat returned and came back {runs['beat']} times",
        ),
        (
            "restart no",
            runs["hold"] == 2,
            f"loop/hold ran {runs['hold']} times, never once on its own account",
        ),
        (
            "reload",
            version["beat"] == 2,
            "loop/beat is running the program it was edited to",
        ),
        (
            "reload restarts a stopped Cell",
            version["hold"] == 2 and runs["hold"] == 2,
            "loop/hold was parked, and the edit is what started it again",
        ),
        (
            "siblings are left alone",
            runs["hold"] == 2,
            "editing loop/beat left loop/hold on its single boot run",
        ),
        (
            "nothing runs in main",
            main_pid not in pids.values(),
            f"main is {main_pid}, no Cell is",
        ),
        (
            "async is one process for the Plane",
            pids["beat"] == pids["hold"],
            f"loop/beat and loop/hold both ran in {pids['beat']}",
        ),
        (
            "mp is one process for the Cell",
            pids["work"] not in (main_pid, pids["beat"]),
            f"solo/work ran in {pids['work']}, on its own",
        ),
    ]
    print("\nverdict, read back from the closed store\n")
    for name, passed, detail in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:<36}{detail}")
    failed = [name for name, passed, _ in checks if not passed]
    print()
    if failed:
        print(f"{len(failed)} check(s) failed: {', '.join(failed)}")
    else:
        print("all good")
    print(f"\nthe Space is still there: nuspace -s {path} ls")


# --- driving it --------------------------------------------------------------


async def live(path):
    """The Space open, from boot to the end of the timeline."""
    # max_parallel=1: nothing in the runtime computes, and a larger budget
    # rations each Plane's Race against a semaphore those arms never give back.
    await nu.arun(open_space(body(), path=path), nu.Context(), max_parallel=1)


def main():
    path = tempfile.mkdtemp(prefix="nuspace-demo-")
    print(f"\nnuspace headless demo   {path}\n")
    print("  loop  async  boot   beat (restart always)   hold (restart no)")
    print("  solo  mp     boot   work (restart always)")
    print(f"  main process is {os.getpid()}")
    asyncio.run(live(path))
    # The read back happens after the loop is gone, on a store nothing holds
    # any more, which is the point: this is what a person would find there.
    verdict(path, os.getpid())


if __name__ == "__main__":
    # The guard is load bearing: the pool spawns, and a child re-imports
    # whatever __main__ is. Without it, opening a Space forks forever.
    main()
