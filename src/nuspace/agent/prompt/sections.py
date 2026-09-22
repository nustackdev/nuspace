"""The prompt as an ordered list of addressable pieces.

A system prompt is not one string, it is a sequence of things a model needs to
know, and which of them a given agent needs depends on the agent. An agent
that never draws has no use for the drawing section; an agent without
``Inspect`` on its surface is being taught a call it cannot make. Both cases
are a caller dropping one name from a tuple, which is why the prompt is a
tuple of named sections rather than a template.

nuagent's, brought across whole. It is the best part of that package and
nothing about it was wrong; what was wrong was the loop it sat in front of.

Nothing here formats anything. The markdown is full of python with dict and
set literals in it, so ``str.format`` would raise on the braces and an
f-string would swallow them; sections compose by concatenation only. The two
facts that do vary ride as marks and are substituted by :func:`str.replace`,
which has no opinion about braces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["Section", "inserted", "replaced", "without"]


@dataclass(frozen=True)
class Section:
    """One named piece of the prompt.

    ``body`` is a callable rather than a string so a section can be generated
    at build time (the catalogue reads the live ``nu.inspect`` records) and so
    a file-backed section does not touch the filesystem until somebody asks
    for a prompt.
    """

    name: str
    body: Callable[[], str] = field(repr=False)

    def render(self) -> str:
        """The section's text, stripped of surrounding blank lines."""
        return self.body().strip("\n")


def without(sections: tuple[Section, ...], *names: str) -> tuple[Section, ...]:
    """``sections`` minus every section named in ``names``."""
    drop = set(names)
    return tuple(section for section in sections if section.name not in drop)


def replaced(sections: tuple[Section, ...], section: Section) -> tuple[Section, ...]:
    """``sections`` with the same-named section swapped for ``section``."""
    return tuple(section if existing.name == section.name else existing for existing in sections)


def inserted(
    sections: tuple[Section, ...],
    section: Section,
    *,
    before: str | None = None,
    after: str | None = None,
) -> tuple[Section, ...]:
    """``sections`` with ``section`` spliced in, or appended when neither anchor is given.

    Raises:
        KeyError: no section is named by the anchor. Appending instead would
            put a section somewhere the caller did not ask for and the wrong
            order is the one thing a prompt cannot be tested for.
    """
    anchor = before or after
    if anchor is None:
        return (*sections, section)
    names = [existing.name for existing in sections]
    if anchor not in names:
        msg = f"no section named {anchor!r}"
        raise KeyError(msg)
    at = names.index(anchor) + (0 if before else 1)
    return (*sections[:at], section, *sections[at:])
