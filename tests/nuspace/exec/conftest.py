"""Shared fixtures for the out-of-process section supervisor tests.

These are integration tests on purpose. Process lifecycle is the thing
under test, and mocking a SIGKILL proves nothing.

Everything shared is a fixture rather than a module-level import, so the
suite does not care which import mode pytest runs in.

Section sources are ``nu.prog`` programs: a python module with an ``out``
entry point that returns a Nu term. ``path`` is the one scope value
nuspace offers, and a source that wants it declares it.
"""

from __future__ import annotations

import asyncio
import os
import textwrap
import time
from types import SimpleNamespace

import pytest

from nuspace.exec import LoopbackHost, Supervisor, Timeouts


# Tight bounds so the suite stays quick. Production defaults are looser.
TEST_TIMEOUTS = Timeouts(ready=20.0, graceful=0.3, term=0.3, kill=2.0)
LADDER_BOUND = TEST_TIMEOUTS.graceful + TEST_TIMEOUTS.term + TEST_TIMEOUTS.kill

SETTLED = {"running", "stopped", "failed", "invalid"}


def program(body: str, *, head: str = "", takes_path: bool = True) -> str:
    """A section source: module preamble, then an ``out`` returning ``body``."""
    params = "path" if takes_path else ""
    expr = textwrap.indent(textwrap.dedent(body).strip(), " " * 8)
    preamble = "import nu\nimport nu.ui\n"
    if head:
        preamble += textwrap.dedent(head).strip() + "\n"
    return f"{preamble}\n\ndef out({params}):\n    return (\n{expr}\n    )\n"


SOURCES = SimpleNamespace(
    # Writes once and finishes: the stopped path.
    oneshot=program("nu.ui.TextRef(path + '.out').set(nu.Str('hello'))"),
    # Standing tick that yields to the loop: cancels cleanly.
    live=program("nu.ForeverDo(nu.Delay(nu.Float(0.05)))", takes_path=False),
    # Standing tick that writes, so a stale generation is observable.
    ticker=program("""
        nu.ForeverDo(
            nu.Delay(nu.Float(0.02)) >> nu.ui.TextRef(path + '.tick').set(nu.Str('x')),
        )
    """),
    # Runs, then dies.
    raises=program("nu.Div(nu.Int(1), nu.Int(0))", takes_path=False),
    # Never constructs: the source does not parse.
    syntax="this is not python (",
    # A tree that spins the event loop with no await point. Cancellation
    # cannot touch this; only a signal can.
    wedge_runtime=program("nu.WhileDo(nu.Bool(True), nu.Noop())", takes_path=False),
    # Wedges in the module body, before an entry point is ever called.
    wedge_compile="while True:\n    pass\n",
    # Wedges *and* ignores SIGTERM. Only SIGKILL ends this one.
    wedge_unkillable=program(
        "nu.WhileDo(nu.Bool(True), nu.Noop())",
        head="import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)",
        takes_path=False,
    ),
    # Reads a ui path through the session, writes what came back.
    reader=program("nu.ui.TextRef(path + '.out').set(nu.ui.InputRef('probe'))"),
    # Subscribes to a ui path and echoes every change.
    echo=program("""
        nu.ReactForever(
            nu.ui.Changed(nu.ui.InputRef('probe')),
            nu.ui.TextRef(path + '.echo').set(nu.ui.InputRef('probe')),
        )
    """),
    # Writes kv scratch and reads it back out through ui.
    kv_round_trip=program(
        """
        Space.state.set_item('k', nu.Str('v'))
        >> nu.ui.TextRef(path + '.out').set(nu.ToStr(Space.state['k']))
        """,
        head="from nuspace.core.shapes import Space",
    ),
    # Reads the same kv key without writing it: scratch is per worker.
    kv_reader=program(
        "nu.ui.TextRef(path + '.out').set(nu.ToStr(Space.state['k']))",
        head="from nuspace.core.shapes import Space",
    ),
)

# A realistic page mix: some standing, some one-shot, all touching nu.ui.
SOURCES.realistic = [
    SOURCES.oneshot,
    SOURCES.live,
    program("""
        nu.ui.TextRef(path + '.a').set(nu.Str('x'))
        | nu.ui.TextRef(path + '.b').set(nu.Str('y'))
    """),
    SOURCES.ticker,
]


def _alive(pid: int) -> bool:
    """True while the pid still exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def _dead_within(pid: int, bound: float) -> float:
    """Poll until the pid is gone. Returns how long that took."""
    start = time.monotonic()
    while _alive(pid):
        if time.monotonic() - start > bound:
            raise AssertionError(f"pid {pid} still alive after {bound}s")
        await asyncio.sleep(0.02)
    return time.monotonic() - start


async def _settled(sup, page_id, *, timeout=20.0, sections=None):
    """Await every section (or the named ones) leaving ``starting``."""
    return await sup.wait_for(page_id, SETTLED, timeout=timeout, sections=sections)


@pytest.fixture
def src():
    """Section sources used across the suite."""
    return SOURCES


@pytest.fixture
def bounds():
    """The Timeouts the fixtures run with, plus the total ladder bound."""
    return SimpleNamespace(timeouts=TEST_TIMEOUTS, ladder=LADDER_BOUND)


@pytest.fixture
def alive():
    """Liveness probe for a pid."""
    return _alive


@pytest.fixture
def dead_within():
    """Await a pid's death within a bound."""
    return _dead_within


@pytest.fixture
def settled():
    """Await a page settling."""
    return _settled


@pytest.fixture
def host():
    """Loopback ui host: records frames, answers reads from a dict."""
    return LoopbackHost()


@pytest.fixture
async def sup(host):
    """A started supervisor with a small warm pool."""
    supervisor = Supervisor(host, pool_size=3, timeouts=TEST_TIMEOUTS)
    await supervisor.astart()
    try:
        yield supervisor
    finally:
        await supervisor.aclose()
