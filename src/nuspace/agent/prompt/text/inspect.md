# Looking things up

The catalogue above covers the nucore atoms only. The fabric surfaces (`nustd.mem`, `nustd.kv` and the rest) are not listed there. Read them with `nu.inspect.Inspect`, a Nu atom that yields text. It is reachable after a bare `import nu`.

Spend a whole turn on a lookup. Return it, do not print it:

```python
import nu


def out():
    return nu.inspect.Inspect("nustd.mem")
```

`Inspect` takes one dotted path. Either a module (`nustd.mem`, `nu.core.arithmetic`) or a fully qualified subject (`nu.core.flows.WhileDo`, `nu.forms.primitives.Int`).

A module renders its docstring and then every Form, Ref and Interaction it exports, one summary line each. That is how you learn a fabric you have not been shown. Nothing is truncated: `nu.inspect.Inspect("nustd.mem")` comes back at over 5000 characters, whole. A subject renders its args, notes, what it yields, and worked examples.

The path must resolve. A path that names nothing ends the run, so inspect the module first and take exact names off it rather than guessing at a subject path.

A lookup pass mutates nothing, so its `state` comes back unchanged. That is expected, not a failure. Use what you read on the next pass to write the real program.

The outcome arrives repr'd, so the whole document is one quoted string with literal `\n` where the newlines are. Read through it.
