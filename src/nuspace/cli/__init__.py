"""The ``nuspace`` command.

Seed a Space with ``plane`` and ``cell``, run it headless with ``run``, look at
it with ``ls``. A Space is a directory one process locks at a time, so the
commands that write want it to themselves and ``run`` holds it while it is up.
"""

from nuspace.cli.main import cli, main


__all__ = ["cli", "main"]
