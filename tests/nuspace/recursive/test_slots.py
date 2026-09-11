"""The recursive slot declaration itself: does the class survive it."""

from __future__ import annotations

import pytest

import nu
from nu import run
from nu.domains.shape.dsl import Slot, SlotDescriptor
from nuspace.core.shapes import Page
from nuspace.recursive import RecursiveShape, SelfSlot, self_slot, self_slot_names

from .conftest import KvNode, MemNode


# --- the silent-wipe trap ---------------------------------------------------


def test_annotation_form_still_wipes_plain_shape():
    """Pin the trap itself, so this suite notices if nu ever fixes it."""

    class Trapped(nu.Shape):
        label: nu.kv.StrRef
        children: nu.kv.ShapesDictRef[str, Trapped]

    assert list(Trapped._slots) == []


def test_recursive_shape_refuses_the_trap_loudly():
    with pytest.raises(TypeError, match="does not resolve"):

        class Guarded(RecursiveShape):
            label: nu.kv.StrRef
            children: nu.kv.ShapesDictRef[str, Guarded]


def test_recursive_shape_keeps_ordinary_annotations_working():
    class Plain(RecursiveShape):
        label: nu.kv.StrRef
        count: nu.kv.IntRef

    assert list(Plain._slots) == ["label", "count"]


# --- every slot present after the recursive declaration ---------------------


def test_all_slots_present_kv():
    assert list(KvNode._slots) == ["label", "count", "route", "route_str", "blocks", "children"]


def test_all_slots_present_mem():
    assert list(MemNode._slots) == ["label", "count", "children"]


def test_page_slots_present():
    assert list(Page._slots) == ["title", "sections", "pages"]


def test_recursive_slot_is_a_real_slot():
    slot = KvNode._slots["children"]
    assert isinstance(slot, Slot)
    assert slot.name == "children"
    assert slot._owner_cls is KvNode
    assert slot.kwargs["shape_type"] is KvNode


def test_recursive_slot_exposes_a_descriptor():
    assert isinstance(KvNode.__dict__["children"], SlotDescriptor)


def test_self_slot_names():
    assert self_slot_names(KvNode) == ("children",)
    assert self_slot_names(Page) == ("pages",)


# --- navigation -------------------------------------------------------------


def test_descends_arbitrarily_deep():
    ref = KvNode.children["a"].children["b"].children["c"].label
    assert ref._owner_shape is KvNode


def test_sibling_slots_reachable_through_recursion():
    assert KvNode.children["a"].blocks["b1"].text is not None


def test_each_access_mints_a_fresh_ref():
    assert KvNode.children is not KvNode.children


# --- loud failures ----------------------------------------------------------


def test_unresolved_declaration_raises_on_read():
    orphan = SelfSlot(nu.kv.ShapesDictRef)
    with pytest.raises(TypeError, match="never resolved"):
        orphan.__get__(None, None)


def test_self_slot_on_a_non_shape_raises():
    # CPython wraps anything __set_name__ raises in a RuntimeError.
    with pytest.raises(RuntimeError) as caught:

        class NotAShape:
            children = self_slot(nu.kv.ShapesDictRef)

    assert isinstance(caught.value.__cause__, TypeError)
    assert "not a Shape" in str(caught.value.__cause__)


def test_self_slot_on_a_ref_without_slot_raises():
    class Bogus:
        pass

    with pytest.raises(RuntimeError) as caught:

        class Broken(RecursiveShape):
            children = self_slot(Bogus)

    assert isinstance(caught.value.__cause__, TypeError)
    assert "no slot() classmethod" in str(caught.value.__cause__)


# --- it still behaves like any other slot -----------------------------------


def test_static_chain_writes_and_reads(kv_ctx):
    run(KvNode.children["a"].children["b"].label.set("deep"), kv_ctx)
    assert run(KvNode.children["a"].children["b"].label, kv_ctx)[0] == "deep"


def test_static_chain_writes_and_reads_mem(mem_ctx, mem_data):
    run(MemNode.children["a"].children["b"].label.set("deep"), mem_ctx)
    assert mem_data == {"children": {"a": {"children": {"b": {"label": "deep"}}}}}
