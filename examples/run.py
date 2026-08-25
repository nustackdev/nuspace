"""Nuspace boot script.

Composes a Nu tree: rocksdb navigator + invisibles proxy server + a
long-running body. The process blocks on the body; external clients
attach via ``nu.proxy.InvisiblesProxy`` (see ``seed_via_proxy.py``).

Run:

    python examples/run.py

Then in another shell:

    python examples/seed_via_proxy.py
"""

from __future__ import annotations

import asyncio

from virtuals import Navigator

import nu
from nu.context.fabric import Provide
from nu.proxy import InvisiblesServer
from nuspace import Space


DB_PATH = "./.nuspace-db"
ADDRESS = "127.0.0.1:19000"


app = nu.With(
    nu.kv.rocksdb_navigator(DB_PATH, tags=(Space,)),
    Provide(
        InvisiblesServer,
        {
            "target": Navigator,
            "address": ADDRESS,
            "transport": "tcp",
            "executor": "threaded",
            "dispatcher": "shared",
        },
        body=nu.ForeverDo(nu.Delay(3600.0)),
    ),
)


if __name__ == "__main__":
    print(f"nuspace: rocksdb at {DB_PATH!r}, proxy on {ADDRESS!r}")
    print("attach with examples/seed_via_proxy.py or your own InvisiblesProxy client")
    asyncio.run(nu.arun(app))
