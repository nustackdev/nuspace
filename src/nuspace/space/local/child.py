"""One driver of ``local.run``, in a process of its own: ``python -m nuspace.space.local.child``.

``local.run`` starts this module twice, ``kernel ROOT`` and ``web ROOT``,
each in a session of its own, so a Ctrl+C on the terminal reaches only
the parent, which stops web first, then the kernel. The entry point's
options come pickled on stdin; the pipe then stays open. When it reads
EOF the parent is gone, whatever way it went, and the child stops itself
as at a Ctrl+C: no driver outlives its supervisor.

Exit status: 0 stopped, :data:`~.supervise.REFUSED` refused (a lock
held, another store format), 1 anything else. Never imported by the
package: ``-m`` runs it fresh.
"""

from __future__ import annotations

import os
import pickle
import signal
import sys
import threading

from .supervise import REFUSED


def watch_parent() -> None:
    """Wait for EOF on stdin, the parent gone or letting go, then stop as Ctrl+C does."""
    # The raw fd, not sys.stdin: a buffered reader held by a daemon thread aborts interpreter shutdown.
    try:
        while os.read(0, 4096):
            pass
    except OSError:
        pass
    os.kill(os.getpid(), signal.SIGINT)


def main(argv: list[str]) -> int:
    """Run the driver ``argv[1]`` on the root ``argv[2]`` until stopped."""
    import nu
    from nuspace import _telemetry
    from nuspace.errors import Refused

    from . import drivers

    what, root = argv[1], argv[2]
    # A parent started in the background may hand down SIGINT ignored: the stop is SIGINT.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    options = pickle.load(sys.stdin.buffer)  # noqa: S301 -- written by our own parent
    threading.Thread(target=watch_parent, name=f"nuspace-{what}-parent", daemon=True).start()
    entry = {"kernel": drivers.kernel, "web": drivers.web}[what]
    try:
        nu.eval_in_loop(nu.compile(entry(root, **options)), nu.Context())
    except KeyboardInterrupt:
        return 0
    except Refused as e:
        print(f"nuspace {what}: {e}", file=sys.stderr)  # noqa: T201
        return REFUSED
    finally:
        _telemetry.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
