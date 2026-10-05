"""The snippets section, generated from the registered snippets rather than written.

A snippet is content with a home: a cell whose prog calls the snippet's
code and whose content lives in the cell's state, where search finds it, a
person edits it and the snippet's ops read and write it. Teaching the model
to put content there, rather than in a program of its own, is what this
section is for, so it carries the rule and then every snippet with its ops.

The ops are read through ``nu.inspect``, the way the catalogue reads the
language, so a snippet registered, an op added or a docstring changed is in
the next prompt with nothing written here. A snippet's import comes from
where its ops or its search live: the package they sit in. A snippet with
neither is listed for what a person may have put on a plane, and is not the
model's to insert.
"""

from __future__ import annotations

import inspect
import sys
from typing import TYPE_CHECKING

from nu.inspect import parse_call
from nuspace.agent.prompt.sections import Section
from nuspace.host import space_registry


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import nu
    from nu.inspect import CallRecord
    from nuspace.ops import Snippet


__all__ = ["registered", "render_snippets", "snippets_section"]


#: The rule, and how to follow it. The example under it is generated from the
#: first snippet that has an op, so it names one that is there.
PREAMBLE = """\
# Snippets

A snippet is a cell a person inserts from the `/` menu. Its prog is a few
lines calling the snippet's code, and what it holds lives in the cell's
state: search finds it there, a person edits it in place, and the snippet's
ops read and write it from any program.

**Content goes in snippets.** Text, a heading, notes, a write-up: insert the
snippet and set what it holds with its ops, in the work cycle. Write a
program of your own only for real behaviour: a live view, something
interactive, a computation. Content baked into a program is content nobody
can search or edit.

`ops.insert_snippet(plane, <snippet>.SNIPPET, into=cell)` adds one at the end
of `plane`, or at `index=`. `into` is a slot it sets to the new cell's id,
`""` when the plane is missing: hold it in `nu.let` and hand it to the ops.
Each op takes the cell id first, and each write op is a commit of
its own, so a program made of them needs no bracket. A read op is bare: wrap
it in `ops.snapshot(...)`.\
"""


def registered() -> tuple[Snippet, ...]:
    """The snippets a space opened here registers: the installed extensions'."""
    return tuple(space_registry().snippets.values())


def snippets_section(snippets: Sequence[Snippet] | None = None) -> Section:
    """The snippets as a prompt section.

    Args:
        snippets: The snippets to teach. :func:`registered` when absent, read
            when the prompt is rendered.

    Returns:
        A Section named ``snippets``.
    """
    return Section(
        "snippets", lambda: render_snippets(registered() if snippets is None else snippets)
    )


def render_snippets(snippets: Sequence[Snippet]) -> str:
    """The rule, one worked example, then one block per snippet, in menu order."""
    parts = [PREAMBLE]
    example = next((s for s in snippets if s.ops), None)
    if example is not None:
        parts.append(_example(example))
    if not snippets:
        parts.append("(no snippets are registered in this space)")
    parts.extend(_block(snippet) for snippet in snippets)
    return "\n\n".join(parts)


def _home(snippet: Snippet) -> str:
    """The package a snippet's ops (or its search) live in, ``""`` when it has neither."""
    first: Callable[..., nu.Nu] | None = next(iter(snippet.ops), snippet.search)
    if first is None:
        return ""
    module = sys.modules[first.__module__]
    return module.__name__ if hasattr(module, "__path__") else module.__name__.rpartition(".")[0]


def _imported(home: str) -> str:
    """The import line that names ``home`` by its last part."""
    parent, _, name = home.rpartition(".")
    return f"from {parent} import {name}" if parent else f"import {name}"


def _record(home: str, op: Callable[..., nu.Nu]) -> CallRecord:
    """``op`` read through ``nu.inspect``, spelled off its snippet's package."""
    name = op.__name__
    qualifier = home.rpartition(".")[2]
    return parse_call(
        op,
        name=name,
        path=f"{home}.{name}",
        owner=home,
        binding="function",
        qualifier=qualifier,
    )


def _example(snippet: Snippet) -> str:
    """A whole program inserting ``snippet`` and calling its first op on the new cell."""
    home = _home(snippet)
    name = home.rpartition(".")[2]
    op = snippet.ops[0]
    rest = list(inspect.signature(op).parameters)[1:]
    args = "".join(f', "<{arg}>"' for arg in rest)
    return f"""\
```python
import nu
from nuspace import ops
{_imported(home)}


def out():
    return nu.let(
        "",
        lambda cell: (
            ops.insert_snippet("<plane>", {name}.SNIPPET, into=cell)
            >> {name}.{op.__name__}(cell{args})
        ),
    )
```"""


def _block(snippet: Snippet) -> str:
    """One snippet: its name and label, what it is for, its import, its ops."""
    lines = [f"## {snippet.name}  ({snippet.label})", ""]
    if snippet.description:
        lines.append(snippet.description)
    home = _home(snippet)
    if not home:
        lines.append("A person inserts it from the `/` menu. It has no ops.")
        return "\n".join(lines)
    lines.append("")
    lines.append(f"    {_imported(home)}")
    lines.append(f"    {home.rpartition('.')[2]}.SNIPPET")
    for op in snippet.ops:
        record = _record(home, op)
        lines.append(f"    {record.call}")
        for text in (record.summary, record.description):
            lines.extend(f"        {line}" for line in text.splitlines() if line.strip())
        lines.extend(f"        {arg.name}: {arg.text}" for arg in record.args if arg.text)
    return "\n".join(lines)
