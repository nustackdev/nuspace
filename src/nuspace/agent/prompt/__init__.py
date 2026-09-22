"""What the model reads before it says anything: nuagent's prompt, plus a space's own.

nuagent already says what Nu is, what a turn looks like and how a run ends,
and none of that changes because the agent happens to live in a Space. What
changes is the world and the way out of it, so the prompt here is nuagent's
default sections with three of ours appended and the surface of this Space
rendered in between:

``space``
    The store is bound *tagged*, by the root Shape class object itself, which
    makes the stock "redeclare every Shape you touch" rule wrong for it.

``speaking``
    A reply is not text. It is one program that draws what happened, draws
    how the person answers next, and appends one line to the conversation.

``drawing``
    How to write the program inside that program: what a turn Cell is, what
    the widget kit offers, and four whole ones.

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

import nuagent

from nuspace.shapes import Space


__all__ = [
    "MODULE_MARK",
    "PROSE",
    "ROOT_MARK",
    "TASK",
    "TEXT_DIR",
    "read",
    "section",
    "system_prompt",
    "text_files",
]


#: Where the prose lives, inside this package.
TEXT_DIR = "text"

#: What the root Shape class is called in the prose. ``Space`` by default, and
#: something else in a subclassed Space, which is why it is not written out.
ROOT_MARK = "$ROOT"

#: Where that class is imported from. Both marks are substituted together and
#: neither is ever right on its own: the import line needs both.
MODULE_MARK = "$MODULE"

#: The file holding what this agent is for. Not a section: nuagent puts the
#: task last, under its own heading, because it is the part a model attends
#: to hardest and the only part that would ever differ per call.
TASK = "task.md"

#: nuspace's own sections, in the order the model reads them, after the
#: surface they are about. ``space`` corrects the stock binding rule, then
#: ``speaking`` says what a reply is, then ``drawing`` says how to write one.
#: Last, because it is the longest and the most concrete, and because a model
#: attends hardest to the end.
PROSE: tuple[str, ...] = ("space", "speaking", "drawing")


def read(filename: str, *, root: type[Space] = Space) -> str:
    """One file out of the shipped ``text/`` directory, with the root filled in.

    Args:
        filename: the file, e.g. ``speaking.md``.
        root: the Space shape class the prose addresses. Its name and the
            module it lives in replace :data:`ROOT_MARK` and
            :data:`MODULE_MARK`, so a chat in a subclassed Space is told
            about *its* root rather than about this one.
    """
    body = resources.files(__package__).joinpath(TEXT_DIR).joinpath(filename).read_text("utf-8")
    return body.replace(ROOT_MARK, root.__name__).replace(MODULE_MARK, root.__module__)


def text_files() -> tuple[str, ...]:
    """Every ``.md`` shipped in ``text/``, sorted. What the rot test counts."""
    directory = resources.files(__package__).joinpath(TEXT_DIR)
    if not directory.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in directory.iterdir() if entry.name.endswith(".md")))


def section(name: str, *, root: type[Space] = Space) -> nuagent.prompt.Section:
    """One of :data:`PROSE` as a nuagent Section, backed by ``text/<name>.md``.

    The body is read when somebody asks for a prompt rather than at import,
    which is nuagent's own rule for a file-backed section and is what lets a
    Space be subclassed after this module is loaded.
    """
    return nuagent.prompt.Section(name, lambda: read(f"{name}.md", root=root))


def system_prompt(*, root: type[Space] = Space) -> str:
    """The whole system prompt for a chat's agent, against one Space's root.

    Args:
        root: the Space shape class. It decides the surface the model is
            shown and the class name every example imports.

    Returns:
        The prompt text: nuagent's defaults, this Space's surface, our three
        sections, and the task last.
    """
    sections = nuagent.inserted(nuagent.DEFAULT_SECTIONS, nuagent.surface_section((root,)))
    for name in PROSE:
        sections = nuagent.inserted(sections, section(name, root=root))
    return nuagent.system_prompt(read(TASK, root=root), sections=sections)
