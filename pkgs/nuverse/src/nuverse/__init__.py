"""nuverse: the extensions a space offers out of the box.

- :mod:`.planes`: what ``+`` creates: ``plain``, ``jobs``, ``runs``,
  ``workers``, ``planes``.
- :mod:`.snippets`: what ``/`` inserts: ``text``, ``program``, ``ticker``,
  ``lens``, ``plane_lens``, ``cell_lens``, and later ``heading``, ``monaco``.

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
    """Every nuverse Plane and snippet, as one extension."""
    from nuspace import Extension

    from .planes import PLANES
    from .snippets import SNIPPETS

    return Extension(planes=PLANES, snippets=SNIPPETS, envs={})
