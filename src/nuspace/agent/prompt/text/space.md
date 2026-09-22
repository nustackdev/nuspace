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
The one place you write that bracket is inside the source of a Cell you draw,
which is a program of its own and holds its own atomicity.

**Prefer `nuspace.ops` to hand-written ref chains.** Each function returns a
Nu term and fixes every invariant the store has -- which Cells a Plane holds
and the order they are tiled in are two spellings of one fact, and these are
the only writers that keep them agreeing:

```python
from nuspace import ops

plane = ops.mint_ordered_id("p")  # python, at module level, not in the term


def out():
    return ops.groups.add("page", plane_id=plane, name="Notes")
```

**Read before you write.** `ops.plane_rows()`, `ops.cell_rows(plane)` and
`ops.cell_statuses(plane)` each yield a list of dicts describing what is
actually there. Returning one of those as your whole program is a good first
turn.

**A write program yields nothing.** It is a Flow, so the observation for a
turn that changed something reads `outcome: None`. That is correct, not a
failure, and not something to report or retry. A read program is the other
way round: its yield is the answer, and that is the turn whose outcome
carries something you can say out loud. The two do not mix in one program: a
read turn that also writes yields `None` and loses the answer it went for.
