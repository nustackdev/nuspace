# Worked programs

## 1. State, a loop, a branch

```python
import nu
import nustd


class Cart(nu.Shape):
    items = nustd.mem.ListRef.slot(str)
    total: nustd.mem.IntRef
    label: nustd.mem.StrRef


PRICES = {"apple": 3, "pear": 5, "fig": 11}

program = (
    Cart.items.init([])
    >> Cart.total.init(0)
    >> nu.ForEachDo(
        nu.Iter(nu.Literal(["apple", "pear", "fig"])),
        Cart.items.append(nu.AttrRef("item"))
        >> Cart.total.set(Cart.total + nu.GetItem(nu.Literal(PRICES), nu.AttrRef("item"))),
        item="item",
    )
    >> nu.IfDo(Cart.total > 10, Cart.label.set("big"), Cart.label.set("small"))
    >> Cart.total.set(Cart.total * 2)
)
```

Final state: `{'items': ['apple', 'pear', 'fig'], 'total': 38, 'label': 'big'}`.

Load-bearing lines:

- `Cart.items.init([])` seeds the slot. Without it the first `append` reads `EMPTY` and the loop writes nothing, silently.
- `nu.ForEachDo(items, body, item="item")` binds the current element as a context attr named `item`. The body reads it with `nu.AttrRef("item")`. It is not a lambda parameter and there is no other way to name it. `nu.ForRangeDo(start, stop, body, step=1, index="index")` binds the same way under `nu.AttrRef("index")`.
- `nu.Iter(nu.Literal([...]))` turns a Python list into a stream. `nu.Literal` is how a Python value enters the tree.
- `Cart.total.set(Cart.total + ...)` reads and writes one Ref in one term. The read is a child, the write is the verb. `Cart.total + x` builds an `Add` term, not an int.
- Python `if` and `for` run at construction time and never appear in the tree. Branch with `IfDo(cond, then, else_)`, `SwitchDo`, `WhileDo`.
- `a >> b` sequences. `b` does not receive `a`'s value; it is not a pipe.
- The program is all Commands, so it yields `None`. The evidence is the state.

## 2. A fabric, and the six kinds

```python
import nu
import nustd


class Meter:
    def __init__(self) -> None:
        self.total = 0.0

    def add(self, a: float, b: float) -> float:
        return a + b

    def bump(self, by: float) -> float:
        self.total += by
        return self.total

    def reset(self) -> None:
        self.total = 0.0


class Calc(nu.Service):
    add = nustd.service.QueryRef.method()
    bump = nustd.service.ActionRef.method()
    wipe = nustd.service.CommandRef.method(name="reset")


class Run(nu.Shape):
    sum: nustd.mem.FloatRef
    running: nustd.mem.FloatRef


app = nu.With(
    nustd.service.bind(Calc, target=Meter()),
    body=nu.Sequential(
        Run.sum.set(Calc.add(a=2, b=3)),
        Run.running.set(Calc.bump(by=10)),
        Run.running.set(Calc.bump(by=Run.sum)),
        Calc.wipe(),
    ),
)
```

Final state: `{'sum': 5, 'running': 15.0}`.

Load-bearing lines:

- Kind per method: `add` is pure, so `QueryRef`. `bump` mutates and returns, so `ActionRef`. `reset` mutates and returns nothing, so `CommandRef`. Picking `QueryRef` for a mutator is the common error.
- `nustd.service.bind(Calc, target=Meter())` is a bracket; `nu.With(bracket, body=...)` binds it for the body only. Move a call outside the `With` and it raises `LookupError`.
- `Calc.bump(by=Run.sum)` passes a Ref as an argument, read when the method Ref resolves.
- `nu.Sequential(a, b, c)` is the explicit form of `a >> b >> c`. `Calc.wipe()` yields nothing and is legal only because `Sequential` is a Flow; the same call in a Query slot fails validation with `scalar_query cannot hold scalar_command`.
