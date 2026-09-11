"""Pages v1: the invariants that are expensive to rediscover by hand.

Three things are worth pinning:

- **Path is the mounting mechanism.** A section mounts the ui refs it names
  under its own prefix and nothing else. Refs it borrows from a sibling stay
  the sibling's. A dynamic deref borrows too, because the outer ref's segment
  is a term rather than a str.
- **The status contract.** `invalid` never compiled, `failed` ran and died,
  and the wire keys are fixed because the executor is built against them.
- **Per-section reconcile.** Editing one block restarts that block and leaves
  its neighbours running.
"""

from __future__ import annotations

import asyncio
import textwrap

import nu
from nu.prog import Diagnostic
from nuspace.web.refs.pages import (
    LocalSupervisor,
    SectionSpec,
    SectionStatus,
    construct_section,
    enumerate_ui_refs,
)
from nuspace.web.refs.pages.store import ordered_blocks, page_node


def program(body: str) -> str:
    """A section: a module with an `out` entry point that declares `path`."""
    expr = textwrap.indent(textwrap.dedent(body).strip(), " " * 8)
    return f"import nu\nimport nu.ui\n\n\ndef out(path):\n    return (\n{expr}\n    )\n"


# -- mounting ----------------------------------------------------------------


def test_enumerate_mounts_only_own_prefix():
    src = program("""
        nu.ui.InputRef(path + '.text').set(nu.Str('x'))
        >> nu.ui.StatRef('sections.s_other.echo').set_value(nu.Str('y'))
    """)
    term = construct_section(src, "sections.s_me")
    fields = enumerate_ui_refs(term, "sections.s_me")
    assert [f["path"] for f in fields] == ["sections.s_me.text"]


def test_enumerate_skips_dynamic_deref():
    # The outer ref's segment is a term, not a str: it borrows whatever the
    # inner ref currently holds. Only the inner ref mounts.
    src = program("""
        nu.ui.StatRef(path + '.out').set_value(
            nu.Str(nu.ui.InputRef(nu.ui.InputRef(path + '.source'))),
        )
    """)
    term = construct_section(src, "sections.s_me")
    paths = {f["path"] for f in enumerate_ui_refs(term, "sections.s_me")}
    assert paths == {"sections.s_me.out", "sections.s_me.source"}


def test_enumerate_dedupes_read_and_write():
    src = program("""
        nu.ui.InputRef(path + '.t').set(nu.Str('a'))
        >> nu.ui.StatRef(path + '.s').set_value(nu.Str(nu.ui.InputRef(path + '.t')))
    """)
    term = construct_section(src, "sections.s1")
    fields = enumerate_ui_refs(term, "sections.s1")
    assert len(fields) == len({(f["type"], f["path"]) for f in fields})


def test_construct_section_rejects_non_nu():
    diag = construct_section("def out(path):\n    return 42\n", "sections.s1")
    assert isinstance(diag, Diagnostic)


# -- ordering ----------------------------------------------------------------


def test_ordered_blocks_sorts_by_order_then_id():
    raw = {
        "s_b": {"order": 0},
        "s_a": {"order": 10},
        "s_c": {"order": 0},
        "s_d": {},  # no order yet: falls to the end, id-ordered
    }
    assert [sid for sid, _ in ordered_blocks(raw)] == ["s_b", "s_c", "s_a", "s_d"]


def test_page_node_ignores_sections():
    node = page_node(
        {"title": "Home", "sections": {"s1": {}}, "pages": {"p2": {"title": "Kid"}}},
        "p1",
        0,
    )
    assert node == {
        "id": "p1",
        "title": "Home",
        "pages": [{"id": "p2", "title": "Kid", "pages": []}],
    }


# -- status contract ---------------------------------------------------------


def test_status_wire_keys_are_fixed():
    wire = SectionStatus("s1", "failed", "Boom: x", 12.5).to_wire()
    assert wire == {
        "section_id": "s1",
        "state": "failed",
        "error": "Boom: x",
        "started_at": 12.5,
    }


# -- supervision -------------------------------------------------------------


A = program("nu.Str('a')")
B = program("nu.Str('b')")
CHANGED = program("nu.Str('CHANGED')")
BROKEN = program("nu.Str('unclosed'")


class _Ctx:
    """Minimal stand-in for a Nu runtime context; nothing here needs it."""


def _sup() -> LocalSupervisor:
    from nuspace.core.shapes import Space

    return LocalSupervisor(_Ctx(), Space)


def test_bad_source_is_invalid_not_failed():
    """A Diagnostic means no tree ever existed, so `invalid`, never `failed`."""
    sup = _sup()
    sup.plan([SectionSpec("s1", BROKEN)])
    st = sup.status("s1")
    assert st["state"] == "invalid"
    # The Diagnostic's message and its line both reach the block chrome.
    assert "does not parse" in st["error"]
    assert "line 6" in st["error"]
    assert st["started_at"] is None


def test_empty_source_is_idle_with_no_fields():
    sup = _sup()
    sup.plan([SectionSpec("s1", "   ")])
    assert sup.status("s1")["state"] == "idle"
    assert sup.fields("s1") == []


def test_plan_leaves_unchanged_running_sections_alone():
    sup = _sup()
    sup.plan([SectionSpec("s1", A), SectionSpec("s2", B)])
    # Pretend both are up.
    for sid in ("s1", "s2"):
        sup._gens[sid].status.state = "running"
        sup._gens[sid].status.started_at = 1.0
    first = sup._gens["s1"]

    sup.plan([SectionSpec("s1", A), SectionSpec("s2", CHANGED)])

    # s1 is the same generation object, untouched.
    assert sup._gens["s1"] is first
    assert sup._gens["s1"].status.state == "running"
    # s2 was recompiled and is queued to relaunch.
    assert sup._gens["s2"].status.state == "idle"
    assert sup._pending == ["s2"]


def test_plan_retires_removed_sections():
    sup = _sup()
    sup.plan([SectionSpec("s1", A), SectionSpec("s2", B)])
    sup.plan([SectionSpec("s1", A)])
    assert set(sup._gens) == {"s1"}


async def test_restart_of_an_invalid_section_re_reports_the_diagnostic():
    seen: list[dict] = []
    sup = _sup()
    sup.on_change(seen.append)
    sup.plan([SectionSpec("s1", BROKEN)])
    await sup.restart("s1")
    assert seen and seen[-1]["section_id"] == "s1"
    assert seen[-1]["state"] == "invalid"


async def test_launch_runs_and_marks_running(monkeypatch):
    """A section that completes cleanly lands on `stopped`, never `failed`."""
    sup = _sup()

    ran = asyncio.Event()

    async def fake_arun(term, ctx):
        ran.set()
        return None, ctx

    monkeypatch.setattr(nu, "arun", fake_arun)
    monkeypatch.setattr(
        "nuspace.web.refs.pages.supervise.auto_flow_atomic",
        lambda term, scope: term,
    )
    monkeypatch.setattr("nuspace.web.refs.pages.supervise.nu", nu)

    seen: list[str] = []
    sup.on_change(lambda w: seen.append(w["state"]))
    sup.plan([SectionSpec("s1", A)])
    await sup.launch()
    await asyncio.wait_for(ran.wait(), timeout=2)
    await asyncio.sleep(0)
    assert seen[:2] == ["starting", "running"]
    assert seen[-1] == "stopped"


async def test_failure_is_reported_as_failed(monkeypatch):
    sup = _sup()

    async def boom(term, ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(nu, "arun", boom)
    monkeypatch.setattr(
        "nuspace.web.refs.pages.supervise.auto_flow_atomic",
        lambda term, scope: term,
    )

    sup.plan([SectionSpec("s1", A)])
    await sup.launch()
    for _ in range(20):
        await asyncio.sleep(0.01)
        if sup.status("s1")["state"] == "failed":
            break
    st = sup.status("s1")
    assert st["state"] == "failed"
    assert "kaboom" in st["error"]
    # It ran before it died, so the start time survives.
    assert st["started_at"] is not None
