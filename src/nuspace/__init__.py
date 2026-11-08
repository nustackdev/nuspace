"""nuspace: a space that runs nu programs as planes and cells.

The top level holds the everyday names only. Two roots, :class:`Space`
(what the space is) and :class:`State` (what programs keep); the record
shapes are under :mod:`nuspace.shapes`. What an op raises is in
:mod:`nuspace.errors`.

Workers import this package: nothing here may pull in a server.
"""

from nuspace import errors
from nuspace.shapes import Space, State


__all__ = ["Space", "State", "errors"]
