"""The apps ``+`` makes, one module each.

Every module defines ``APP``: an :class:`~nuspace.App`, or None while it is
still a placeholder, which is left out.
"""

from __future__ import annotations

from . import chat, job, page, planes, runs, workers


__all__ = ["APPS"]


#: Every app ready to register, in picker order.
APPS = tuple(
    module.APP for module in (page, runs, workers, planes, job, chat) if module.APP is not None
)
