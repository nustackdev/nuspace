"""Walking the page substrate: addresses in, plain python out.

Every function here is pure except for the address builders, which build
Nu refs and evaluate nothing. Reading is the caller's job, because the
read has to happen inside an atom with a runtime in hand.

Ordering: blocks sort by the ``order`` int slot, ties broken by id. The
interactions renormalize ``order`` to ``index * ORDER_STEP`` after any
structural change, so gaps never close and a reorder is a rewrite of one
small int per block.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "KINDS",
    "KIND_PROGRAM",
    "KIND_PROSE",
    "MAX_BLOCKS",
    "MAX_CHILD_PAGES",
    "MAX_PAGE_DEPTH",
    "ORDER_STEP",
    "as_str_list",
    "kind_of",
    "ordered_blocks",
    "page_node",
    "page_ref",
    "parent_pages",
]


MAX_CHILD_PAGES = 200
MAX_PAGE_DEPTH = 12
MAX_BLOCKS = 300
ORDER_STEP = 10

KIND_PROSE = "prose"
KIND_PROGRAM = "program"
KINDS = (KIND_PROSE, KIND_PROGRAM)


def page_ref(space_root: type[Shape], path: list[str]) -> Any:  # noqa: ANN401
    """Return the ``PageRef`` at ``path``; empty path = the root page."""
    ref = space_root.pages
    for pid in path:
        ref = ref.pages[str(pid)]
    return ref


def parent_pages(space_root: type[Shape], path: list[str]) -> tuple[Any, str]:
    """Split ``[pid..., pid]`` into (parent pages container, page_id)."""
    if not path:
        raise ValueError("page path is empty; the root page has no parent")
    return page_ref(space_root, path[:-1]).pages, str(path[-1])


def page_node(data: object, pid: str | None, depth: int) -> dict[str, Any]:
    """One rail node from an ``extract()`` blob. Blocks are not shown."""
    if not isinstance(data, dict):
        return {"id": pid, "title": str(pid or ""), "pages": []}
    kids_raw = data.get("pages")
    kids: list[dict[str, Any]] = []
    if isinstance(kids_raw, dict) and depth < MAX_PAGE_DEPTH:
        for kid, blob in sorted(kids_raw.items())[:MAX_CHILD_PAGES]:
            kids.append(page_node(blob, str(kid), depth + 1))
    return {"id": pid, "title": str(data.get("title") or (pid or "")), "pages": kids}


def ordered_blocks(raw: object) -> list[tuple[str, dict[str, Any]]]:
    """Sort a sections ``extract()`` blob by ``order`` then id.

    ``order`` may be missing (pre-``order`` stores, or a set_item that
    skipped it) or read back as a Nu sentinel rather than an int. Both
    fall back to id order, which is creation order because
    ``mint_ordered_id`` is time-prefixed.
    """
    if not isinstance(raw, dict):
        return []
    items: list[tuple[str, dict[str, Any]]] = []
    for sid, blob in raw.items():
        if isinstance(blob, dict):
            items.append((str(sid), blob))

    def key(pair: tuple[str, dict[str, Any]]) -> tuple[int, str]:
        order = pair[1].get("order")
        return (int(order) if isinstance(order, int) else 1 << 30, pair[0])

    items.sort(key=key)
    return items


def kind_of(blob: dict[str, Any]) -> str:
    """A block's kind, defaulting to ``program`` for anything unrecognised."""
    kind = blob.get("kind")
    return kind if kind in KINDS else KIND_PROGRAM


def as_str_list(raw: object) -> list[str]:
    """Coerce a wire value to a list of strings; anything else is empty."""
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(s) for s in raw]
