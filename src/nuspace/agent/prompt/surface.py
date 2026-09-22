"""The app surface section: the Shapes and Services this agent is bound to.

The catalogue is the language. This is the world. A model handed only the
catalogue knows every atom it can compose and nothing about the thing it was
hired to change, so its first two turns go on discovering that a Board exists
and what a task record holds. Both facts are already on the app's classes,
exactly, and ``nu.inspect`` reads them, so front-loading them costs one
rendered page and saves the turns.

They are two sections rather than one on purpose. The catalogue is what the
model may write; the surface is what the model may write *against*, and it is
the caller's, not nu's. Merging them would tell the model that ``Board`` and
``ForEachDo`` are the same kind of fact, and the first thing it does with
that is treat one of them as a thing it can look up in the language.

Entry-summary level, never deeper
---------------------------------

A Shape page is one line per slot: name, kind, type, config. A Ref page is
the whole verb table, 83 lines for a single ``StrRef`` slot, so six slots
inlined is 400 lines of prompt for verbs the model may never call. The
two-level discipline ``nu.inspect`` is built on applies here for the same
reason it applies there: list what exists, let the reader descend. Every
entry line carries the dotted path that resolves it, so descending is
copying a string into ``Inspect``.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING

from nu.inspect import (
    ServiceRecord,
    catalogue_services,
    catalogue_shapes,
    parse_entry,
    parse_service,
    parse_shape,
)
from nu.inspect.entry import is_service, is_shape
from nuspace.agent.prompt.sections import Section
from nuspace.agent.shapes import Run


if TYPE_CHECKING:
    from nu.inspect import Entry, Record


__all__ = [
    "app_records",
    "render_surface",
    "surface_section",
]


#: Framing. Without it the section is a list of names, and a list of names is
#: read as reference material rather than as the thing to act on. Three facts
#: have to land: these are yours, they are already bound, and this is how you
#: get from a name to its verbs. The binding warning is load bearing - a model
#: that helpfully wraps its term in its own ``nu.Provide`` shadows the host's
#: fabric, and every write it makes lands in a dict nobody reads.
PREAMBLE = """\
# Your app surface

These are the Shapes and Services of the app you are running inside. They are
not examples. They are the world the task is about, and their fabrics are
already provided around your program.

- **Do not bind anything.** No `nu.Provide`, no `nu.With`, no `nu.Context` in
  your module. A binding of your own shadows the host's, and every write you
  make then lands in a store nobody reads: the program runs, the state does
  not change, and nothing raises.
- **Declare what you touch.** Your module is loaded on its own, so repeat the
  declaration of each Shape you write against at module level: same class
  name, same slot names, same Ref types as listed here. Addressing is by slot
  name, so a matching declaration reaches the host's world. Write every slot
  with `.slot()`, never with the annotation form: a slot declared as
  `total: nustd.mem.IntRef` is dropped when the host loads your module, and the
  Shape comes back without it.
- **The verbs are not here.** Each entry is one line: name, kind, type,
  config. To learn what a slot or a method can do, spend a turn returning
  `nu.inspect.Inspect("<the entry's path>")`, copying the path off the entry
  line exactly.

The declaration form to repeat, with the fabric off the heading and the type
and config off the entry line:

```python
import nu
import nustd


class Ledger(nu.Shape):
    total = nustd.mem.IntRef.slot()
    rows = nustd.mem.ShapesDictRef.slot(Row, str)
```\
"""


def surface_section(app: tuple[ModuleType | type, ...], *, run: type | None = Run) -> Section:
    """The app surface as a prompt section.

    Args:
        app: the modules and classes that make up the agent's world. A module
            contributes every Shape and Service it declares, in export order;
            a class contributes itself. Mixing the two is normal, since an app
            commonly declares its Shapes in one module and hands the agent a
            subset.
        run: the run Shape, rendered last. It is on the surface by default
            because the model cannot end the run without redeclaring it, and
            a fact every agent needs does not belong at every call site. Pass
            ``KVRun`` for a durable app, or ``None`` for a single ``turn``,
            which has no loop to end.

    Returns:
        A Section named ``surface``.

    Example:
        >>> from nuspace.agent.prompt import DEFAULT_SECTIONS, inserted, surface_section
        >>> sections = inserted(DEFAULT_SECTIONS, surface_section((Board, Task)))
    """
    return Section("surface", lambda: render_surface(app, run=run))


def app_records(app: tuple[ModuleType | type, ...]) -> tuple[Record, ...]:
    """One ShapeRecord or ServiceRecord per declared class, in the given order.

    Args:
        app: modules and classes, as for :func:`surface_section`.

    Returns:
        The records, deduplicated by path so a class named both directly and
        through its module appears once.

    Raises:
        TypeError: for anything that is neither a module nor a declared Shape
            or Service class. Silently dropping it would render a surface
            missing the thing the caller cared most about.
    """
    records: list[Record] = []
    for item in app:
        if isinstance(item, ModuleType):
            records.extend(catalogue_shapes(item))
            records.extend(catalogue_services(item))
        elif is_shape(item):
            records.append(parse_shape(item))
        elif is_service(item):
            records.append(parse_service(item))
        else:
            msg = f"not a module, Shape or Service: {item!r}"
            raise TypeError(msg)
    seen: set[str] = set()
    unique: list[Record] = []
    for record in records:
        if record.path not in seen:
            seen.add(record.path)
            unique.append(record)
    return tuple(unique)


def render_surface(app: tuple[ModuleType | type, ...], *, run: type | None = Run) -> str:
    """The framing, then one block per declared class, then the run Shape.

    ``run`` comes last and separately from the app's own classes: it is not
    part of the app, it is how the model ends the loop, and an app with
    nothing bound still has one.
    """
    records = app_records(app)
    parts = [PREAMBLE]
    if not records:
        parts.append("(nothing is bound on your surface)")
    parts.extend(_block(record) for record in records)
    if run is not None:
        parts.append(_block(parse_shape(run)))
    return "\n\n".join(parts)


def _block(record: Record) -> str:
    """One class: heading, prose, notes, entries."""
    kind = "service" if isinstance(record, ServiceRecord) else "shape"
    fabric = _fabric(record)
    where = f"  ({fabric})" if fabric else ""
    lines = [f"## {kind}  {record.path}{where}", ""]
    if record.summary:
        lines.append(record.summary)
    for note in record.notes:
        lines.append(f"- {note}")
    entries: tuple[Entry, ...] = record.entries  # type: ignore[attr-defined]
    lines.append("")
    lines.append(f"entries ({len(entries)})")
    lines.extend(_entry_line(entry) for entry in entries)
    return "\n".join(lines).strip()


def _entry_line(entry: Entry) -> str:
    """Name, kind, type, config. The same four facts nu.inspect prints."""
    text = f"  {entry.name:<18} {entry.kind:<7} {entry.type}"
    return f"{text}  {entry.config}" if entry.config else text


def _fabric(record: Record) -> str:
    """The fabric the class's Refs live in, e.g. ``nustd.mem``, or "" when mixed.

    A slot's Ref class is where the fabric is actually written down, and the
    entry line does not carry it: ``StrRef`` alone does not say whether the
    write is ephemeral or durable, and the model has to name the fabric to
    repeat the declaration. Anything but a single unanimous ``nustd.<fabric>``
    is left off rather than guessed at.

    Every fabric lives under ``nustd`` as of nu 0.5.0. Nothing under ``nu``
    itself is one, so a Ref whose module does not start there yields nothing
    rather than a guess, and the heading simply loses its fabric.
    """
    target = record.target
    if not isinstance(target, type):
        return ""
    fabrics = set()
    for entry in record.entries:  # type: ignore[attr-defined]
        found = parse_entry(target, entry.name)
        module = getattr(getattr(found, "target", None), "__module__", "")
        parts = module.split(".")
        if len(parts) >= 2 and parts[0] == "nustd":
            fabrics.add(f"{parts[0]}.{parts[1]}")
    return fabrics.pop() if len(fabrics) == 1 else ""
