"""Content: typed, findable items any cell can write, read and show.

A prog is code, content is data. A kind is a :class:`Content` over a plain
``nu.Shape``, its schema, read off the generic argument at run time::

    class Text(nu.Shape):
        value = nustd.kv.StrRef.slot()


    class TextContent(nuspace.Content[Text], name="Text"):
        @classmethod
        def match(cls, item: Text, *, text: nu.StrArg | Unset = UNSET) -> nu.Bool: ...

A kind declares its name on the class, by convention the class's own less
``Content``, and an installed package registers it with a
:class:`~nuspace.ext.ContentSpec` in its extension
(``Extension(contents=(ContentSpec(TextContent),))``), which says how a
space presents it: its label, description and icon. Registered, it is named
``<package>.<name>``, ``nuverse.Text``, like a Plane or a Cell
(:func:`~nuspace.ext.kind_name`). The store and every address key by that name, never by
where the class lives, so moving a module leaves items in place. Any
process, a worker too, finds the spec a name names, and the kind through
it, from the installed entry points (:func:`~nuspace.ext.content_spec`): a
headless op needs the name only, never a host's registry.

An item lives in nuspace's store, never in a program's own state, at a
fixed place per kind and scope (:mod:`nuspace.shapes.contents`). Its
address is plain data, ``(kind, scope, id)``, a scope being ``(level, id)``
with the level one of :data:`CELL`, :data:`PLANE` and :data:`SPACE`::

    TextContent.cell("summary")           # this cell's item "summary", a Text
    TextContent.plane("title")            # this plane's
    TextContent.space("readme")           # the space's
    TextContent.at(("cell", c), "summary")  # any item, by its address
    TextContent.items(("cell", c))        # every item of a scope, by id
    TextContent.new(("cell", c), into=r)  # a fresh item, its id set in r
    TextContent.find(text="basil")        # (address, item) of every match

``cell`` and ``plane`` are relative, like ``CellState`` and ``PlaneState``:
the kernel lands them under the cell and plane running the program
(:mod:`nuspace.shapes.reroot`). Every accessor is typed to return the
kind's Shape, as a ``DictRef[K, S][key]`` is, so fields chain as on any
Shape.

Two modules: :mod:`.kind`, the kind and one item, and :mod:`.search`, finding
items across the store.

Workers import this package: nothing here may pull in a server.
"""

from . import search
from .kind import (
    CELL,
    INPUTS,
    ITEM_PREFIX,
    LEVELS,
    NUMBER_INPUT,
    PLANE,
    SPACE,
    SWITCH_INPUT,
    TEXT_INPUT,
    UNSET,
    Content,
    Drawing,
    SearchField,
    Unset,
    address,
    kind_name,
)
from .search import matched, scopes


__all__ = [
    "CELL",
    "INPUTS",
    "ITEM_PREFIX",
    "LEVELS",
    "NUMBER_INPUT",
    "PLANE",
    "SPACE",
    "SWITCH_INPUT",
    "TEXT_INPUT",
    "UNSET",
    "Content",
    "Drawing",
    "SearchField",
    "Unset",
    "address",
    "kind_name",
    "matched",
    "scopes",
    "search",
]
