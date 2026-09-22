# What Nu is

`Nu = Ref | Interaction`. Every node in a Nu program is one of the two.

**Ref** names an address: a dict slot, a db row, a config key, an http endpoint, a method on an object. It carries the address, not the value at the address. Used as a child, a Ref executes and yields the value at its address. Refs are the only atoms that touch the world: every READ and WRITE happens at a Ref. No Refs in a subtree, no effects in that subtree.

**Interaction** describes what to do with Refs and with other Interactions: read, write, compute, branch, iterate, compose. Refs name, Interactions describe.

**Fabric** is an addressable space where Refs live, and the machinery that resolves them. A python dict, rocksdb, an http api, a Ray cluster are each a fabric. **Context** is the union of the fabrics a program runs against. Fabrics execute.

The program is the Interaction. The world is in the Context. The same program against a different Context is a different world, with no edit to the program.

**Mutation of the Context is the core dimension.** `Context v0` -> `Interaction(Ref)` -> `Context v1`, with `v1 != v0`. That is the whole model. A composition that mutates nothing is meaningless. An atom is observable in its place iff it mutates Context, or yields a value consumed by an ancestor whose chain eventually mutates Context. Anything else is wasted compute. Nu will not stop you from building a read-only program; it just does nothing.

Building a term is free and total: it constructs a nested immutable value, runs no code, checks nothing, and cannot fail. Rejection happens later, at `nu.run`, as a `ValidationError`.

# The six kinds

| Kind | Mutates Context | Yields a value | Role |
| --- | --- | --- | --- |
| Ref | no (own) | yes | address atom; only path to Context |
| Query | no | yes | pure value producer |
| Command | yes | no | pure mutator |
| Action | yes | yes | mutates and yields, atomically |
| Flow | no (own) | no | composes mutating children |
| Span | transparent | transparent | cross-cutting wrapper |

Naming tells you the kind:

- Bare verb (`If`, `Map`, `Add`, `Len`) is a **Query**. Yields a value or a stream.
- `*Do` suffix (`IfDo`, `ForEachDo`, `WhileDo`, `ForRangeDo`, `SwitchDo`) is a **Flow**. Its body slot needs a mutator, not a value.

`Cart.total.set(3)` is a Command. `Cart.items.pop()` is an Action: it removes the element and yields it, which is why it exists instead of a Command then a Query. `nu.TryCatch`, `nu.Retry`, `nu.Timeout`, `nu.Transaction`, `nu.Snapshot` are Spans: they wrap any Nu and forward the body's yield unchanged.

# Composition

`a >> b` sequential, `a | b` parallel, `a & b` race. `nu.Sequential(a, b)` is the explicit form of `a >> b`.

What may nest in what is one rule: **a value slot needs something that yields; a body slot needs something that mutates.** So Ref, Query and Action go anywhere a value is wanted; a Command never does, because it yields nothing. A Flow's body takes Commands, Actions and Flows. On a Flow, a Ref or Query is accepted only in a parameter slot (`cond`, `items`, `count`, `start`, `stop`), never as a body peer.

```python
import nu
import nustd


class Cart(nu.Shape):
    total = nustd.mem.IntRef.slot()
    items = nustd.mem.ListRef.slot(str)
    prices = nustd.mem.ListRef.slot(int)


ok = Cart.total.set(Cart.total * 2)  # Ref read inside a Command's value slot
ok2 = Cart.total.set(Cart.prices.pop())  # Action in a value slot: it yields
bad = nu.Add(Cart.total.set(1), 2)  # builds fine; nu.run raises ValidationError:
# "scalar_query cannot hold scalar_command"
```

# Where a Python model gets Nu wrong

You know Python. Nu is written in Python and is not Python. These eight mismatches account for most failures.

**1. Python control flow does not survive into the program.** `if`, `for`, `while`, `and`, `or`, `not` in your builder run at construction time, in the interpreter building the tree. They never appear in the program. Worse, `bool(term)` is always `True`, so a python `if` on a Nu condition silently takes the first branch forever.

```python
import nu
import nustd


class Cart(nu.Shape):
    total = nustd.mem.IntRef.slot()


# WRONG: this branch is decided while building. The else is unreachable, always.
def decided():
    if Cart.total > 3:
        return Cart.total.set(0)
    return Cart.total.set(1)


# RIGHT: the branch is a node in the program.
def out():
    return nu.IfDo(Cart.total > 3, Cart.total.set(0), Cart.total.set(1))
```

Same for loops: a python `for` unrolls at build time and a term is not iterable (`TypeError`). Use `nu.ForEachDo` / `nu.ForRangeDo` / `nu.WhileDo`. Python `and`/`or`/`not` on terms are wrong too; use `nu.And`, `nu.Or`, `.not_()`.

**2. Loop atoms bind the element as a context attr, not as a lambda parameter.** There is no closure over the element. `ForEachDo(items, body, item="item")` writes each element into the context under `item`; the body reads it back with `nu.AttrRef("item")`. `ForRangeDo(start, stop, body, *, step=1, index="index")` does the same under `index`. This is impossible to guess.

```python
import nu
import nustd


class Cart(nu.Shape):
    items = nustd.mem.ListRef.slot(str)


def out():
    return Cart.items.init([]) >> nu.ForEachDo(
        nu.Iter(nu.Literal(["a", "b"])),
        Cart.items.append(nu.AttrRef("item")),
    )
```

**3. `>>` is not a pipe and not a shift.** It sequences. The left runs, then the right. The right does **not** receive the left's value. To move a value between steps, write it to a Ref and read that Ref.

**4. A Command yields nothing, so a Command chain evaluates to `None`.** That is success, not failure. `nu.run` returns `(value, ctx)`; for an effect-only program the value is `None` and all the evidence is in the mutated state. Do not re-do work because you saw `None`.

**5. Unset slots go EMPTY, then INVALID, and can fail in silence.** Reading an unset slot yields the `EMPTY` sentinel. Any operation over it collapses to `INVALID`. Then, depending on the verb, the write either raises `ValueError: cannot store sentinel value` or does nothing at all and raises nothing.

```python
# WRONG: items is unset. This writes nothing and raises nothing.
wrong = Cart.items.append("book")

# RIGHT: seed the slot, or guard the read.
right = Cart.items.init([]) >> Cart.items.append("book")
guarded = nu.IfDo(Cart.items.exists(), Cart.items.append("book"))
```

Test with `.exists()`, `.missing()`, `.is_empty()`, `nu.IsEmpty`, `nu.IsInvalid`. Prefer `.init(...)` to seed before use.

**6. Refs are class attributes, used unbound.** `Cart.total.set(3)` is a term, not a method call on an instance. A Shape is never instantiated. There is no `Cart()`.

**7. Nothing in the tree reaches a fabric that was not provided around it.** An unbound Ref is `LookupError: No binding for: dict[Cart]` at run time, not at build time.

**8. `nu.print(...)` writes to the host process's stdout and yields `None`.** It is not how you see a value. To see a value, make it the program's yield: `return` it.

```python
seen = nu.inspect.Inspect("nu.core.flows.WhileDo")  # yields the text
unseen = nu.print(nu.inspect.Inspect("nu.core.flows.WhileDo"))  # yields None
```
