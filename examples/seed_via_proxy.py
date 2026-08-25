"""Proxy seed: attaches to a running ``examples/run.py`` and writes into it.

Requires ``examples/run.py`` running in another shell. Uses
``InvisiblesProxy`` to bind the remote ``Navigator`` locally; the same
nuspace refs then execute over the wire.

Run:

    python examples/run.py            # in one shell
    python examples/seed_via_proxy.py # in another

The proxy transport is invisibles RPC (TCP), not HTTP. Async runtime
only.
"""

from __future__ import annotations

import asyncio

from virtuals import Navigator

import nu
from nu.proxy import InvisiblesProxy
from nuspace import Space


ADDRESS = "127.0.0.1:19000"


TEXT_SNIPPET = "nu.Str('added via proxy')"


seed = (
    Space.apps.add(TEXT_SNIPPET, policy="always", app_id="a_proxy")
    >> Space.pages.set_item("via-proxy", {"title": "Via Proxy", "sections": {}})
    >> Space.pages["via-proxy"].sections.add(
        "nu.Str('proxy-planted section')",
        policy="on_navigate",
        section_id="s_from_proxy",
    )
)


app = InvisiblesProxy(
    Navigator,
    address=ADDRESS,
    body=nu.kv.auto_flow_atomic(seed, scope=Space),
)


if __name__ == "__main__":
    print(f"seeding via proxy at {ADDRESS!r}...")
    asyncio.run(nu.arun(app))
    print("done.")
