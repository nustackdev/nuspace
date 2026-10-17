"""The ``nuspace`` command: make a space, run it, list what extends it.

Pure command line, not an API: nothing imports it, workers least of all.

A space is a directory one process locks at a time, so a command that opens
one holds it for as long as it is up.
"""

from .main import cli, main


__all__ = ["cli", "main"]
