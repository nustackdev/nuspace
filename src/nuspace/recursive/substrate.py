"""Substrate adapters for addressing a ref at a path built at run time.

A Ref's own read and write resolve their path from the tree, so they take a
node id and walk the parent chain. Deep addressing already has the path as
data and needs the other half: the same storage mechanics, with the path
handed in.

Each substrate exposes that half under three operations:

``splice``   build the full path from the ref's construct-time prefix, the
             runtime segments and the edge slot the recursion goes through.
``read``     open at a path and lift the result, with an async twin.
``write``    store an already-lowered value at a path, vivifying every level.
             Lowering stays on the caller so the async path can await it.

Substrates are picked by the plug-points a ref actually carries, not by
importing a backend and testing ``isinstance``. ``nu.kv`` refs carry
``_fetch_and_ensure_parent_view``; ``nu.mem`` refs carry ``_root_data``.
Anything else raises a NotImplementedError naming the ref class, so a new
backend fails loudly rather than reading the wrong address.

Path layout is the thing that actually differs. ``nu.kv`` paths are
``((address, view_or_value_type), ...)`` because the navigator stamps the
declared view class on every level it vivifies; ``nu.mem`` paths are bare
keys because a dict has nothing to stamp. Splicing is therefore per
substrate, and the kv splice carries the *declared* view types for the
levels it invents, never the container layer's default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol

from nu.lang import EMPTY


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = [
    "Substrate",
    "substrate_for",
]


class Substrate(Protocol):
    """The three path-taking operations deep addressing needs from a backend."""

    @staticmethod
    def splice(
        base: tuple,
        segments: Sequence[object],
        edge: str,
        edge_marker: object,
        item_marker: object,
    ) -> tuple:
        """Full path: the ref's prefix with the runtime descent spliced above the leaf."""
        ...

    @staticmethod
    def read(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Value at ``path``, lifted; EMPTY when nothing is stored there."""
        ...

    @staticmethod
    async def aread(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Async twin of :meth:`read`."""
        ...

    @staticmethod
    def write(ref: StructuredRef, rt: Runtime, path: tuple, value: object) -> None:
        """Store an already-lowered ``value`` at ``path``, materializing every level."""
        ...


def _is_container(ref: StructuredRef) -> bool:
    """True when the ref addresses a container slot rather than a leaf value."""
    return hasattr(ref, "_apply_facet")


class KvSubstrate:
    """``nu.kv``: paths of ``(address, marker)`` pairs through virtuals Views."""

    name: ClassVar[str] = "kv"

    @staticmethod
    def splice(
        base: tuple,
        segments: Sequence[object],
        edge: str,
        edge_marker: object,
        item_marker: object,
    ) -> tuple:
        """Interleave ``(edge, seg)`` pairs above the leaf, each carrying its view type."""
        middle = tuple(
            entry
            for seg in segments
            for entry in ((edge, edge_marker), (seg, item_marker))
        )
        return base[:-1] + middle + (base[-1],)

    @staticmethod
    def read(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Open ``path`` read-only (never vivifying) and lift what is there."""
        if not _is_container(ref):
            # PrimitiveRef._read already opens the parent, subscripts, maps a
            # missing key onto EMPTY and lifts. Exactly the leaf read, minus
            # the path resolution we are replacing.
            return ref._read(rt, path)  # type: ignore[attr-defined]
        from nu.kv.paths import ViewPathSer
        from nu.kv.refs.base import _resolve_navigator, _resolve_storage_ctx

        scope = ref._root_shape
        nav = _resolve_navigator(rt, scope, path)
        storage_ctx = _resolve_storage_ctx(rt, scope, path)
        view = nav.open_at_path(ViewPathSer(path), storage_ctx)
        return ref._apply_facet(view)  # type: ignore[attr-defined]

    @staticmethod
    async def aread(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Same door as :meth:`read`: virtuals navigation has no async form."""
        return KvSubstrate.read(ref, rt, path)

    @staticmethod
    def write(ref: StructuredRef, rt: Runtime, path: tuple, value: object) -> None:
        """Ensure every ancestor with its declared view type, then store the leaf."""
        parent = ref._fetch_and_ensure_parent_view(rt, path)  # type: ignore[attr-defined]
        key, view_class = path[-1]
        if _is_container(ref):
            parent.set_child_container_as(key, value, view_class)
        else:
            parent[key] = value


class MemSubstrate:
    """``nu.mem``: paths of bare keys through nested Python dicts."""

    name: ClassVar[str] = "mem"

    @staticmethod
    def splice(
        base: tuple,
        segments: Sequence[object],
        edge: str,
        edge_marker: object,
        item_marker: object,
    ) -> tuple:
        """Interleave ``edge, seg`` above the leaf; a dict carries no type marker."""
        middle = tuple(entry for seg in segments for entry in (edge, seg))
        return base[:-1] + middle + (base[-1],)

    @staticmethod
    def read(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Walk the nested dicts; any missing or unsubscriptable level is EMPTY."""
        cur = ref._root_data(rt)  # type: ignore[attr-defined]
        try:
            for key in path:
                cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return EMPTY
        return ref._lift(cur)

    @staticmethod
    async def aread(ref: StructuredRef, rt: Runtime, path: tuple) -> object:
        """Same walk as :meth:`read`, through the async lift."""
        cur = ref._root_data(rt)  # type: ignore[attr-defined]
        try:
            for key in path:
                cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return EMPTY
        return await ref._alift(cur)

    @staticmethod
    def write(ref: StructuredRef, rt: Runtime, path: tuple, value: object) -> None:
        """Vivify every intermediate dict, then assign the leaf key."""
        cur = ref._root_data(rt)  # type: ignore[attr-defined]
        for key in path[:-1]:
            if isinstance(cur, dict) and key not in cur:
                cur[key] = {}
            cur = cur[key]
        cur[path[-1]] = value


def substrate_for(ref: StructuredRef) -> type[Substrate]:
    """Pick the substrate adapter matching the plug-points ``ref`` carries.

    Args:
        ref: the leaf Ref the deep address ends on.

    Returns:
        The adapter class. Probing for the plug-points rather than the
        backend module means a ref that fills the same seam works with no
        change here.

    Raises:
        NotImplementedError: the ref fills neither seam. The message names
            the ref class rather than guessing an address.

    Example:
        >>> substrate_for(Page.title).name
        'kv'
    """
    if hasattr(ref, "_fetch_and_ensure_parent_view"):
        return KvSubstrate
    if hasattr(ref, "_root_data"):
        return MemSubstrate
    msg = (
        f"deep addressing has no substrate for {type(ref).__name__}: it "
        f"carries neither _fetch_and_ensure_parent_view (kv) nor _root_data "
        f"(mem)."
    )
    raise NotImplementedError(msg)
