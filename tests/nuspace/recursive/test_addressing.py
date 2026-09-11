"""Reading and writing a recursive shape at a path known only at run time.

Every tree here goes through ``validate(compile(tree))`` before it runs, so
a law regression shows up as a law failure rather than as a wrong value.
"""

from __future__ import annotations

import pytest

from nu import arun, run
from nu.lang import EMPTY, INVALID, compile, validate
from nuspace.core.shapes import Page, Space
from nuspace.recursive import Descent, GetDeep, SetDeep, descent_for, substrate_for
from nuspace.recursive.substrate import KvSubstrate, MemSubstrate

from .conftest import KvLeaf, KvNode, MemBag, MemNode


def gated(tree):
    """Run the law gate on a tree and hand it back."""
    validate(compile(tree))
    return tree


# --- the descent resolves at build time -------------------------------------


def test_descent_found_from_the_single_self_slot():
    d = descent_for(KvNode.label)
    assert isinstance(d, Descent)
    assert d.edge == "children"


def test_descent_carries_declared_view_types():
    from virtuals.views import DictView

    d = descent_for(KvNode.label)
    assert d.edge_marker is DictView
    assert d.item_marker is DictView


def test_descent_on_page():
    assert descent_for(Page.title).edge == "pages"


def test_descent_refuses_a_non_recursive_edge():
    with pytest.raises(TypeError, match="not KvNode"):
        descent_for(KvNode.label, edge="blocks")


def test_descent_refuses_an_unknown_edge():
    with pytest.raises(TypeError, match="no slot 'nope'"):
        descent_for(KvNode.label, edge="nope")


def test_descent_refuses_a_shape_that_does_not_recurse():
    with pytest.raises(TypeError, match="no self-recursive slot"):
        descent_for(KvLeaf.text)


# --- substrate dispatch -----------------------------------------------------


def test_substrate_dispatch():
    assert substrate_for(KvNode.label) is KvSubstrate
    assert substrate_for(MemNode.label) is MemSubstrate


def test_substrate_refuses_an_unknown_ref():
    class Foreign:
        pass

    with pytest.raises(NotImplementedError, match="Foreign"):
        substrate_for(Foreign())


# --- kv: write vivifies, read comes back ------------------------------------


def test_three_deep_write_vivifies_into_empty_kv(kv_ctx):
    run(gated(SetDeep(KvNode.label, ["a", "b", "c"], "deep")), kv_ctx)
    assert run(KvNode.children["a"].children["b"].children["c"].label, kv_ctx)[0] == "deep"


def test_deep_write_is_visible_to_the_static_chain_kv(kv_ctx):
    run(SetDeep(KvNode.count, ["a", "b"], 42), kv_ctx)
    assert run(KvNode.children["a"].children["b"].count, kv_ctx)[0] == 42


def test_read_at_a_runtime_path_kv(kv_ctx):
    run(KvNode.children["x"].children["y"].label.set("found"), kv_ctx)
    assert run(gated(GetDeep(KvNode.label, ["x", "y"])), kv_ctx)[0] == "found"


def test_roundtrip_at_many_depths_kv(kv_ctx):
    for depth in range(5):
        path = [f"p{i}" for i in range(depth)]
        run(SetDeep(KvNode.label, path, f"d{depth}"), kv_ctx)
        assert run(GetDeep(KvNode.label, path), kv_ctx)[0] == f"d{depth}"


def test_empty_path_addresses_the_leaf_kv(kv_ctx):
    run(SetDeep(KvNode.label, [], "root"), kv_ctx)
    assert run(KvNode.label, kv_ctx)[0] == "root"


def test_missing_path_reads_empty_kv(kv_ctx):
    run(KvNode.children["a"].children["b"].label.set("here"), kv_ctx)
    assert run(GetDeep(KvNode.label, ["a", "zz"]), kv_ctx)[0] is EMPTY


def test_sibling_branches_do_not_collide_kv(kv_ctx):
    run(SetDeep(KvNode.label, ["a", "b"], "L"), kv_ctx)
    run(SetDeep(KvNode.label, ["a", "c"], "R"), kv_ctx)
    assert run(GetDeep(KvNode.label, ["a", "b"]), kv_ctx)[0] == "L"
    assert run(GetDeep(KvNode.label, ["a", "c"]), kv_ctx)[0] == "R"


def test_a_deep_write_does_not_disturb_the_intermediate_kv(kv_ctx):
    run(SetDeep(KvNode.label, ["a"], "mid"), kv_ctx)
    run(SetDeep(KvNode.label, ["a", "b"], "leaf"), kv_ctx)
    assert run(GetDeep(KvNode.label, ["a"]), kv_ctx)[0] == "mid"
    assert run(GetDeep(KvNode.label, ["a", "b"]), kv_ctx)[0] == "leaf"


# --- kv: the leaf can be a container, not just a scalar ---------------------


def test_container_leaf_reads_at_a_runtime_path_kv(kv_ctx):
    run(KvNode.children["a"].blocks["b1"].text.set("hi"), kv_ctx)
    view = run(GetDeep(KvNode.blocks, ["a"]), kv_ctx)[0]
    assert list(view.keys()) == ["b1"]


def test_container_leaf_honours_the_facet_kv(kv_ctx):
    run(KvNode.children["a"].blocks["b1"].text.set("hi"), kv_ctx)
    eager = run(GetDeep(KvNode.blocks.eager, ["a"]), kv_ctx)[0]
    assert dict(eager) == {"b1": {"text": "hi"}}


# --- the path is an ordinary child ------------------------------------------


def test_path_supplied_by_a_ref_kv(kv_ctx):
    run(KvNode.route.set(["a", "b"]), kv_ctx)
    run(KvNode.children["a"].children["b"].label.set("via-ref"), kv_ctx)
    assert run(gated(GetDeep(KvNode.label, KvNode.route)), kv_ctx)[0] == "via-ref"


def test_path_supplied_by_a_query_kv(kv_ctx):
    """The browser case: a slash route out of storage, split in the tree."""
    run(KvNode.route_str.set("a/b"), kv_ctx)
    run(KvNode.children["a"].children["b"].label.set("via-query"), kv_ctx)
    tree = GetDeep(KvNode.label, KvNode.route_str.split("/"))
    assert run(gated(tree), kv_ctx)[0] == "via-query"


def test_path_from_a_cross_fabric_ref_kv(kv_ctx, mem_data):
    ctx = kv_ctx.bind(dict, mem_data, MemBag)
    run(MemBag.route.set(["a", "b"]), ctx)
    run(KvNode.children["a"].children["b"].label.set("cross"), ctx)
    assert run(gated(GetDeep(KvNode.label, MemBag.route)), ctx)[0] == "cross"


# --- mem -------------------------------------------------------------------


def test_three_deep_write_vivifies_into_empty_mem(mem_ctx, mem_data):
    run(gated(SetDeep(MemNode.label, ["a", "b", "c"], "deep")), mem_ctx)
    assert mem_data == {
        "children": {"a": {"children": {"b": {"children": {"c": {"label": "deep"}}}}}}
    }


def test_read_at_a_runtime_path_mem(mem_ctx):
    run(SetDeep(MemNode.count, ["a", "b"], 7), mem_ctx)
    assert run(GetDeep(MemNode.count, ["a", "b"]), mem_ctx)[0] == 7


def test_missing_path_reads_empty_mem(mem_ctx):
    assert run(GetDeep(MemNode.label, ["nope"]), mem_ctx)[0] is EMPTY


def test_deep_write_is_visible_to_the_static_chain_mem(mem_ctx):
    run(SetDeep(MemNode.label, ["a", "b"], "x")   , mem_ctx)
    assert run(MemNode.children["a"].children["b"].label, mem_ctx)[0] == "x"


# --- bad input fails loudly -------------------------------------------------


def test_string_path_refused(kv_ctx):
    with pytest.raises(TypeError, match="sequence of segments"):
        run(GetDeep(KvNode.label, "ab"), kv_ctx)


def test_non_iterable_path_refused(kv_ctx):
    with pytest.raises(TypeError, match="not iterable"):
        run(GetDeep(KvNode.label, 3), kv_ctx)


def test_sentinel_path_reads_invalid(kv_ctx):
    assert run(GetDeep(KvNode.label, KvNode.route), kv_ctx)[0] is INVALID


def test_sentinel_path_refuses_to_write(kv_ctx):
    with pytest.raises(ValueError, match="sentinel path"):
        run(SetDeep(KvNode.label, KvNode.route, "x"), kv_ctx)


def test_sentinel_value_refused(kv_ctx):
    with pytest.raises(ValueError, match="sentinel value"):
        run(SetDeep(KvNode.label, ["a"], KvNode.count), kv_ctx)


# --- laws -------------------------------------------------------------------


def test_setdeep_declares_one_write_on_slot_zero():
    assert SetDeep._mutates.value == frozenset({0})


def test_getdeep_declares_no_write():
    assert not getattr(GetDeep, "_mutates", None)


def test_law_gate_passes_on_a_composed_tree():
    tree = SetDeep(KvNode.label, ["a"], "x") >> SetDeep(KvNode.count, ["a"], 1)
    validate(compile(tree))


# --- async twins ------------------------------------------------------------


async def test_async_write_then_read_kv(kv_ctx):
    await arun(SetDeep(KvNode.label, ["a", "b"], "async"), kv_ctx)
    assert (await arun(GetDeep(KvNode.label, ["a", "b"]), kv_ctx))[0] == "async"


async def test_async_missing_path_kv(kv_ctx):
    assert (await arun(GetDeep(KvNode.label, ["nope"]), kv_ctx))[0] is EMPTY


async def test_async_write_then_read_mem(mem_ctx, mem_data):
    await arun(SetDeep(MemNode.label, ["a", "b"], "async"), mem_ctx)
    assert mem_data == {"children": {"a": {"children": {"b": {"label": "async"}}}}}
    assert (await arun(GetDeep(MemNode.label, ["a", "b"]), mem_ctx))[0] == "async"


async def test_async_path_from_a_ref_kv(kv_ctx):
    run(KvNode.route.set(["a", "b"]), kv_ctx)
    run(KvNode.children["a"].children["b"].label.set("aref"), kv_ctx)
    assert (await arun(GetDeep(KvNode.label, KvNode.route), kv_ctx))[0] == "aref"


# --- the nuspace Page tree, end to end --------------------------------------


def test_page_tree_addressed_by_a_runtime_path(kv_ctx):
    path = ["docs", "guides", "intro"]
    run(gated(SetDeep(Page.title, path, "Intro")), kv_ctx)
    assert run(GetDeep(Page.title, path), kv_ctx)[0] == "Intro"
    assert run(Page.pages["docs"].pages["guides"].pages["intro"].title, kv_ctx)[0] == "Intro"


def test_page_tree_under_space(kv_ctx):
    run(SetDeep(Space.pages.title, ["docs"], "Docs"), kv_ctx)
    assert run(Space.pages.pages["docs"].title, kv_ctx)[0] == "Docs"
