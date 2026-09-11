"""Seed some apps, run them, watch them write.

Two launches over two stores: one with fewer apps than the warm pool, one
with more, so the pool has to grow. Each launch prints the plan, the tree,
the law gate, the live worker processes while the tree is running, and what
the apps left in kv afterwards.

    uv run python examples/run_apps.py
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import shutil
import subprocess
import sys
from pathlib import Path

import nu
import nu.kv
from nu.lang import compile as nu_compile
from nu.lang import validate
from nuspace.core.shapes import Space
from nuspace.runner import demo_apps, free_port, manifest, runner_tree, seed_store


ROOT = Path("/tmp/nuspace-runner-demo")  # noqa: S108


def descendants() -> int:
    """Every process under this one, however deep, straight out of ps."""
    out = subprocess.run(
        ["/bin/ps", "-A", "-o", "pid=,ppid="],
        capture_output=True,
        text=True,
        check=True,
    )
    kids: dict[str, list[str]] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            kids.setdefault(parts[1], []).append(parts[0])
    seen: set[str] = set()
    stack = list(kids.get(str(os.getpid()), []))
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(kids.get(pid, []))
    return len(seen)


async def sample(label: str, every: float, times: int) -> None:
    """Print what is alive a few times while the tree is up."""
    for _ in range(times):
        await asyncio.sleep(every)
        workers = sorted(p.name for p in multiprocessing.active_children())
        print(f"  [{label}] workers alive: {len(workers)} {workers}")
        print(f"  [{label}] processes under this one: {descendants()}")


async def state(path: str) -> dict:
    tree = nu.With(
        nu.kv.rocksdb_navigator(path, read_only=True),
        body=nu.kv.auto_flow_atomic(nu.dict(Space.state.items()), scope=Space),
    )
    rows, _ = await nu.arun(tree, nu.Context())
    return dict(rows or {})


async def one(label: str, *, apps: int, warm: int, ticks: int, show_tree: bool = False) -> None:
    path = str(ROOT / label)
    shutil.rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)

    seeded = demo_apps(apps, ticks=ticks, every=0.1)
    await seed_store(path, seeded)
    print(f"\n== {label}: seeded {len(seeded)} apps, warm={warm}")

    # The same two steps launch() runs, spelled out so the tree is visible.
    app_ids = await manifest(path)
    tree, slots = runner_tree(
        app_ids,
        path=path,
        address=f"127.0.0.1:{free_port()}",
        warm=warm,
    )
    validate(nu_compile(tree))
    print("  law gate: validate(compile(tree)) passed")
    print(f"  plan: {len(slots)} workers")
    for slot in slots:
        print(f"    {slot.tag} -> {list(slot.apps) or 'idle (warm)'}")
    if show_tree:
        print(tree)

    watcher = asyncio.create_task(sample(label, 0.4, 3))
    await nu.arun(tree, nu.Context(), max_parallel=max(8, len(slots) * 8))
    await watcher

    print("  kv after the run:")
    for key, value in sorted((await state(path)).items()):
        print(f"    {key} = {value}")


async def main() -> None:
    await one("small", apps=1, warm=3, ticks=5, show_tree=True)
    await one("grown", apps=5, warm=2, ticks=5)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
