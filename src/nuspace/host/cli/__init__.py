"""The ``nuspace`` command: open a space, served in a browser or headless.

A space is a directory one process locks at a time, so either command holds
it for as long as it is up.
"""

from .main import cli, main


__all__ = ["cli", "main"]
