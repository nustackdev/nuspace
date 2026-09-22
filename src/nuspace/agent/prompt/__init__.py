"""What the model reads before it says anything.

Named sections, in order, with the prose on disk as markdown and the two
generated ones built from ``nu.inspect``. The order is the argument: who you
are, what Nu is, where values live, how to write it, what it looks like done,
what a pass is, how a pass ends, how to look things up, what exists, what your
world is, what a turn is, what an answer is, how to draw one, and only then
what to do. The task goes last because it is the only part that changes per
caller and a model attends hardest to the end of what it is given.

Four of the sections are nuspace's own and the rest came from nuagent, which
is where this shape was worked out:

``space``
    The store is bound *tagged*, by the root Shape class object itself, which
    makes the stock "redeclare every Shape you touch" rule wrong for it.

``cycles``
    A turn is two cycles. One does the thing and one says what was done, and
    what a program is for is different in each.

``speaking``
    An answer is not text and it is not a write either. It is a value the host
    builds a Cell out of, checks, and appends.

``drawing``
    How to write that Cell: what the widget kit offers, and whole ones.

The prose is in ``text/*.md``, shipped as package data and read through
``importlib.resources`` so it resolves the same out of a wheel and out of an
editable checkout. It is a prompt: it gets rewritten most days, and a prompt
nobody can open is a prompt nobody improves.

Nothing here is a format string. The markdown is full of python with dict and
set literals in it, so ``str.format`` would raise on the braces and an
f-string would swallow them. The two facts that do vary, the root Shape class
and the module it is imported from, ride as :data:`ROOT_MARK` and
:data:`MODULE_MARK` and are substituted by :func:`str.replace`, which has no
opinion about braces.
"""

from __future__ import annotations

from importlib import resources

from nuspace.agent.prompt.catalogue import DEFAULT_MODULES, catalogue_section
from nuspace.agent.prompt.sections import Section, inserted, replaced, without
from nuspace.agent.prompt.surface import surface_section
from nuspace.shapes import Space


__all__ = [
    "ANSWER",
    "DEFAULT_MODULES",
    "DRAWING",
    "LANGUAGE",
    "MESSAGES",
    "MODULE_MARK",
    "OPENING",
    "PROSE",
    "ROOT_MARK",
    "TASK",
    "WORLD",
    "Section",
    "inserted",
    "read",
    "replaced",
    "section",
    "sections_for",
    "system_prompt",
    "text_files",
    "without",
]


#: Where the prose lives, inside this package.
TEXT_DIR = "text"

#: What the root Shape class is called in the prose. ``Space`` by default, and
#: something else in a subclassed Space, which is why it is not written out.
ROOT_MARK = "$ROOT"

#: Where that class is imported from. Both marks are substituted together and
#: neither is ever right on its own: the import line needs both.
MODULE_MARK = "$MODULE"

#: The language sections, in order. What Nu is and how a pass works, none of
#: which changes because the agent happens to live in a Space.
LANGUAGE: tuple[str, ...] = (
    "role",
    "thesis",
    "fabrics",
    "crashcourse",
    "examples",
    "protocol",
    "finish",
    "inspect",
)

#: The sections about this world, in order, read after the generated two they
#: are about. Last, because they are the longest and the most concrete, and
#: because a model attends hardest to the end.
WORLD: tuple[str, ...] = ("space", "cycles", "speaking", "drawing")

#: The two sections a job agent has no use for: it never draws and never
#: speaks, so teaching it either is teaching it a move it cannot make.
DRAWING: tuple[str, ...] = ("speaking", "drawing")

#: Every section backed by a file, which is what the rot test counts against
#: what is shipped.
PROSE: tuple[str, ...] = LANGUAGE + WORLD

#: What this agent is for. Not a section: the task goes last, under its own
#: heading, because it is the part a model attends to hardest and the only
#: part that would ever differ per caller.
TASK = "task.md"

#: The first user message of every turn, before the ids and the conversation.
OPENING = "opening.md"

#: And the message that starts the answer cycle. It is a message rather than a
#: section because it arrives in the middle of a turn: the model has already
#: read the whole prompt and done the work, and this is the host telling it
#: which cycle it is in now.
ANSWER = "answer.md"

#: Every file that is a message rather than a section.
MESSAGES: tuple[str, ...] = (TASK, OPENING, ANSWER)


def read(filename: str, *, root: type[Space] = Space) -> str:
    """One file out of the shipped ``text/`` directory, with the root filled in.

    Args:
        filename: the file, e.g. ``speaking.md``.
        root: the Space shape class the prose addresses. Its name and the
            module it lives in replace :data:`ROOT_MARK` and
            :data:`MODULE_MARK`, so a chat in a subclassed Space is told about
            *its* root rather than about this one.
    """
    body = resources.files(__package__).joinpath(TEXT_DIR).joinpath(filename).read_text("utf-8")
    return body.replace(ROOT_MARK, root.__name__).replace(MODULE_MARK, root.__module__)


def text_files() -> tuple[str, ...]:
    """Every ``.md`` shipped in ``text/``, sorted. What the rot test counts."""
    directory = resources.files(__package__).joinpath(TEXT_DIR)
    if not directory.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in directory.iterdir() if entry.name.endswith(".md")))


def section(name: str, *, root: type[Space] = Space) -> Section:
    """One file-backed section, backed by ``text/<name>.md``.

    The body is read when somebody asks for a prompt rather than at import,
    which is what lets a Space be subclassed after this module is loaded.
    """
    return Section(name, lambda: read(f"{name}.md", root=root))


def sections_for(root: type[Space] = Space, *, drawing: bool = True) -> tuple[Section, ...]:
    """Every section this agent reads, in order.

    Args:
        root: the Space shape class. It decides the surface the model is
            shown and the class name every example imports.
        drawing: whether this agent answers by drawing. ``False`` for a job
            agent, which does the work cycle and nothing after it.

    Returns:
        The sections, language first, then the two generated from
        ``nu.inspect``, then the ones about this world.
    """
    world = WORLD if drawing else tuple(name for name in WORLD if name not in DRAWING)
    return (
        *(section(name, root=root) for name in LANGUAGE),
        catalogue_section(),
        surface_section((root,)),
        *(section(name, root=root) for name in world),
    )


def system_prompt(
    *,
    root: type[Space] = Space,
    task: str | None = None,
    sections: tuple[Section, ...] | None = None,
    drawing: bool = True,
) -> str:
    """The whole system prompt, against one Space's root.

    Args:
        root: the Space shape class.
        task: what this agent is for. The chat's own, out of ``task.md``, when
            absent, which is what a chat made by pressing ``+`` gets.
        sections: the sections to render, in order. Derived from
            :func:`sections_for` when absent, which is what every caller does.
        drawing: whether this agent answers by drawing. Ignored when
            ``sections`` is given.

    Returns:
        The prompt text.
    """
    chosen = sections_for(root, drawing=drawing) if sections is None else sections
    parts = [one.render() for one in chosen]
    parts.append("# Task\n\n" + (read(TASK, root=root) if task is None else task).strip())
    return "\n\n".join(parts) + "\n"
