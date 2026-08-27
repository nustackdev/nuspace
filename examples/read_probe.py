"""Read-back probe.

Run examples/seed_direct.py first to populate the DB. Then:

    python examples/read_probe.py          # direct navigator
    python examples/read_probe.py proxy    # via a running examples/run.py

Exercises get / iter through Space refs. Before the auto_flow_atomic fix
in nu.kv.tree, a bare top-level ref-touching subtree failed with
``LookupError: No binding for: SnapshotProtocol[Space](site=..., path=...)``
because the read never landed inside a Snapshot bracket.
"""

from __future__ import annotations

import asyncio

import nu
from nuspace import Space


DB_PATH = "./nuspace.db"
ADDRESS = "127.0.0.1:19000"


def _reads() -> nu.Nu:
    # Bare ref-touching subtree. auto_flow_atomic wraps it in Snapshot(scope=Space).
    return nu.Dict.of(
        hello_snippet=Space.apps.apps["a_hello"].snippet,
        home_title=Space.pages.pages["p_home"].title,
        welcome_snippet=Space.pages.pages["p_home"].sections["s_welcome"].snippet,
        app_keys=nu.Collect(nu.Iter(Space.apps.apps)),
        page_keys=nu.Collect(nu.Iter(Space.pages.pages)),
        home_section_keys=nu.Collect(nu.Iter(Space.pages.pages["p_home"].sections)),
    )


def _print(label: str, value: dict) -> None:
    print(label)
    for k, v in value.items():
        print(f"  {k} = {v!r}")


def _run_direct() -> None:
    body = nu.kv.auto_flow_atomic(_reads(), scope=Space)
    app = nu.With(nu.kv.rocksdb_navigator(DB_PATH, tags=(Space,)), body=body)
    value, _ = asyncio.run(nu.arun(app))
    _print("[direct]", value)


def _run_via_proxy() -> None:
    from virtuals import Navigator

    from nu.proxy import InvisiblesProxy

    body = nu.kv.auto_flow_atomic(_reads(), scope=Space)
    app = InvisiblesProxy(
        Navigator,
        address=ADDRESS,
        transport="tcp",
        tag=Space,
        body=body,
    )
    value, _ = asyncio.run(nu.arun(app))
    _print(f"[proxy@{ADDRESS}]", value)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    if mode == "proxy":
        _run_via_proxy()
    else:
        _run_direct()
