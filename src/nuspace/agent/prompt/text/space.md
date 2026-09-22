# Working the space

Your world is a live nuspace, and it is durable. Its store is bound tagged by
the root Shape class object itself, which makes the redeclaration rule above
**wrong for it**. Import the real class instead:

```python
from nuspace import ops
from $MODULE import $ROOT
```

A `$ROOT` you declare yourself is a different class object, so the tagged
store does not resolve against it: your program runs, nothing raises, and
every write lands in a store nobody reads. Import, never redeclare. `Plane`
and `Cell` are reached through `$ROOT`, so you rarely name them at all;
inspect them when you need to.

**Do not bracket your program.** The host already holds the atomic bracket
over the store. No `nustd.kv.auto_flow_atomic`, no `nu.With`, no `nu.Provide`.
The one place you write that bracket is inside the source of a Cell you hand
back, which is a program of its own and holds its own atomicity.

**Prefer `nuspace.ops` to hand-written ref chains.** Each function returns a
Nu term and fixes every invariant the store has. Which Cells a Plane holds and
the order they are tiled in are two spellings of one fact, and these are the
only writers that keep them agreeing:

```python
from nuspace import ops

plane = ops.mint_ordered_id("p")  # python, at module level, not in the term


def out():
    return ops.groups.add("page", plane_id=plane, name="Notes")
```

**Read before you write.** `ops.plane_rows()`, `ops.cell_rows(plane)` and
`ops.cell_statuses(plane)` each yield a list of dicts describing what is
actually there. Returning one of those as your whole program is a good first
pass.

**A write program yields nothing.** It is a Flow, so the observation for a
pass that changed something reads `outcome: None`. That is correct, not a
failure, and not something to report or retry. A read program is the other way
round: its yield is the answer, and that is the pass whose outcome carries
something you can say out loud. The two do not mix in one program: a read pass
that also writes yields `None` and loses the answer it went for.

**Three ops belong to the chat rather than to the space**, and the panel ones
take the panel's two ids off the first message of the turn:

```python
ops.chat.note("<the ui plane>", "<the panel cell>", "work", "renamed the Notes plane", root=$ROOT)
ops.chat.submit("<the chat plane>", "<the chat cell>", "text", ui_plane_id="<the ui plane>", root=$ROOT)
```

`note` is yours and is the only one you call directly: it puts one line in the
panel the person is watching, and it is a write, so it goes in the programs
that write. `submit` is never called from a program you run; it goes inside
the Cell you hand back, on a click. `ops.chat.say` and `ops.chat.draw` exist
and are the host's: the answer cycle is what appends a Cell and a message, and
it does it only after checking that the Cell builds.
