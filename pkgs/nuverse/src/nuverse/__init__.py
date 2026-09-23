"""nuverse: the extensions a space offers out of the box.

- :mod:`.apps`: what ``+`` makes: ``page``, and later ``job``, ``chat``.
- :mod:`.snippets`: what ``/`` inserts: ``prose``, ``program``, ``ticker``,
  and later ``heading``, ``monaco``.

nuspace finds this package through the ``nuspace.extensions`` entry point,
which names :func:`extension`. Nothing is imported here at module scope:
workers import cell programs, and a program never needs the registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["extension"]


def extension() -> Extension:
    """Every nuverse app and snippet, as one extension."""
    from nuspace import Extension

    from .apps import APPS
    from .snippets import SNIPPETS

    return Extension(apps=APPS, snippets=SNIPPETS, envs={})
