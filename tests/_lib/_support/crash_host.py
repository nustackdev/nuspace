"""A host that opens a space, runs plane runs, says so, and waits to be killed.

For the reap test: run as ``python -m _support.crash_host <data dir> <marker>``.
Once every cell run is live it writes ``<marker>`` (JSON: the plane run ids
and the workers' pids) and parks until SIGKILL ends it, as a crash would.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from _support.kernel import FOREVER, Kernel, live, opened


async def _main(data: str, marker: str) -> None:
    k: Kernel = await opened("nuspace-crash", data=data, spares=0)
    runs = []
    for backend in ("async", "mp"):
        p, _ = await k.plane(FOREVER, FOREVER, backend=backend)
        runs.append(await k.start(p, by="crash"))
    rows = [
        await k.run_row(r, lambda x: x["cells"] and all(live(c) for c in x["cells"]), 30)
        for r in runs
    ]
    pids = [w["handle"]["pid"] for row in rows for w in row["workers"]]
    Path(marker).write_text(json.dumps({"runs": runs, "pids": pids}))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1], sys.argv[2]))
