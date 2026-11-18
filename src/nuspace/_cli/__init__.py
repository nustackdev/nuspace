"""The ``nuspace`` command: make a space, run it, list what extends it.

Pure command line, not an API: nothing imports it, workers least of all.

A command that runs a driver holds that driver's lock for as long as it is
up: one infra, one kernel and one web per space.
"""

from .main import cli, main


__all__ = ["cli", "main"]
