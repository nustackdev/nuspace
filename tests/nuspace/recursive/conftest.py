"""Shapes and real backends for the recursive-addressing suite.

No mocks anywhere: mem runs against a plain dict in the Context, kv runs
against a real virtuals stack parametrized over InMemoryStorage and
RocksDB, so the vivification path is exercised on the backend that
actually stamps view markers.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from virtuals import Navigator
from virtuals.codecs import BinaryCodec
from virtuals.tkv.storage import StorageProtocol, TransactionProtocol

import nu
from nu import Context
from nuspace.recursive import RecursiveShape, self_slot


if TYPE_CHECKING:
    from collections.abc import Generator


# --- shapes: one recursive tree per fabric ----------------------------------


class KvLeaf(nu.Shape):
    """A non-recursive child shape, so a page can hold more than scalars."""

    text = nu.kv.StrRef.slot()


class KvNode(RecursiveShape):
    """The kv recursive shape under test."""

    label = nu.kv.StrRef.slot()
    count = nu.kv.IntRef.slot()
    route = nu.kv.PrimitiveListRef.slot()
    route_str = nu.kv.StrRef.slot()
    blocks = nu.kv.ShapesDictRef.slot(KvLeaf)
    children = self_slot(nu.kv.ShapesDictRef)


class MemNode(RecursiveShape):
    """The mem recursive shape under test."""

    label = nu.mem.StrRef.slot()
    count = nu.mem.IntRef.slot()
    children = self_slot(nu.mem.ShapesDictRef)


class MemBag(nu.Shape):
    """A mem shape holding a path, for the cross-fabric key case."""

    route = nu.mem.ListRef.slot(str)


# --- mem backend ------------------------------------------------------------


@pytest.fixture
def mem_data() -> dict:
    """The live root dict the mem refs read and write in place."""
    return {}


@pytest.fixture
def mem_ctx(mem_data: dict) -> Context:
    """Context with the root dict bound under the MemNode scope."""
    return Context().bind(dict, mem_data, MemNode)


# --- kv backend, over two real storages -------------------------------------


@pytest.fixture(params=["inmemory", "rocksdb"])
def kv_storage(request: pytest.FixtureRequest) -> Generator[StorageProtocol, None, None]:
    """A real virtuals storage, once in memory and once on RocksDB."""
    if request.param == "inmemory":
        from virtuals.storages.mem import InMemoryStorage

        storage = InMemoryStorage(codec=BinaryCodec())
        with storage:
            yield storage
        return

    rocks = pytest.importorskip("virtuals.storages.rocksdb")
    path = Path(tempfile.mkdtemp(prefix="nuspace-recursive-"))
    storage = rocks.RocksDBStorage(str(path), codec=BinaryCodec())
    try:
        with storage:
            yield storage
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def kv_ctx(kv_storage: StorageProtocol) -> Generator[Context, None, None]:
    """Context bundling a Navigator and a read-write transaction."""
    with kv_storage.transaction() as tx:
        yield Context().bind(Navigator, Navigator(kv_storage)).bind(TransactionProtocol, tx)
