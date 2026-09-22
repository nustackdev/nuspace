# The pass protocol

A **pass** is one reply from you plus the one program in it. Passes are what
everything here is counted in, and the panel beside the chat numbers them
against a ceiling, so `pass 3 of 100` is the third pass of the cycle you are
in. The ceiling is far away and it is not a target: work takes what it takes
and you are the one who says when it is done.

What does stop you is repeating yourself. Fail three passes in a row with the
same first line and the cycle gives up, because a model handed the same
diagnostic three times has stopped reading it. Failing in new ways is fine,
it means you are getting further in. So when an `outcome` comes back the same
as last time, change the approach rather than the spelling.

## Your reply

Write exactly one fenced code block per reply. The host splits your reply on
the fence and takes the **first** block. A second block is ignored, so never
quote a broken earlier version above your fix. If your reply contains no
complete fenced block at all, the whole reply is used as source.

Every reply must carry a code block. Prose is not an action: the host runs
programs and nothing else, so a reply without one runs nothing, changes
nothing, and costs a pass. You get back `NO CODE BLOCK: your reply contained
no fenced code block, so nothing ran`.

**The prose around the block is not thrown away.** Whatever you write before
your first fence lands in the panel the person is watching, cut short, one
line per pass. So write one sentence saying what this pass is for and stop
there. A summary at the end reaches nobody, because by then the pass is over.

The block is a Python module:

```python
import nu
import nustd


class World(nu.Shape):
    notes = nustd.mem.ListRef.slot(str)
    count = nustd.mem.IntRef.slot()


def out():
    return World.notes.init([]) >> World.notes.append("n1") >> World.count.set(nu.Len(World.notes))
```

Rules for the module:

- `import nu` at the top, and `import nustd` too whenever you name a fabric
  Ref. `nu` is the language; `nustd` is where every fabric lives.
  `nustd.mem.StrRef` with only `import nu` is a `NameError` and costs you the
  pass.
- Declare Shapes at module level.
- Define `def out()`. It takes **no arguments**. The host calls it with none.
- `out()` returns one Nu term. That term is the program.

## What the host does with it

The source lands in a `ProgramRef`. `LoadNu` loads the module and calls the
entry point `out`, which constructs the term. `Eval` runs it. Your program
runs **exactly once** per pass.

## What you get back

The next user message is exactly this, and nothing else:

    outcome: <repr of what the term yielded>
    state: <the world after the program ran>

You never see a traceback, a tool result, or the host's stdout.

Read it like this:

- `outcome` is the yield, repr'd. Newlines arrive as a literal `\n` inside one
  quoted string.
- **A Command yields nothing, so `outcome: None` is normal.** A chain of
  writes that completely succeeded reports `outcome: None`. It is not a
  failure and not silence. `state` is where the evidence of your work is. Read
  `state` before rewriting anything: if the write landed, do not do it again.
- `nu.print(...)` writes to the **host's** stdout. You never see it, and the
  outcome is `None`. To read a value, `return` it from `out()`.

## When it fails

Five failure paths. All come back as the `outcome`, in the same slot a
successful yield uses. None of them ends anything. A diagnostic is an ordinary
message you are expected to read and fix on the next pass.

No code: your reply had no fenced block, so nothing was run.

- `NO CODE BLOCK: your reply contained no fenced code block, so nothing ran.`

Construction failed: the source did not parse, or `out()` raised while
building the term.

- `CONSTRUCTION FAILED: source does not parse: '(' was never closed (line 5)`
- `CONSTRUCTION FAILED: entry point 'out' raised: AttributeError: module 'nu' has no attribute 'Nope' (line 5)`

The line number counts lines of the source you sent, starting at 1.

Runtime failed: the term built and then raised while running.

- `RUNTIME FAILED: division by zero`

The last two only happen in the answer cycle, and they are about what you
handed back rather than about the module that handed it back. **They are not
saying your reply was broken.** Read "Answering" for what they mean.

- `NOT AN ANSWER: an answer is a dict with two keys in it ...`
- `THE CELL DID NOT BUILD: source does not parse: invalid syntax (line 9)`

Never write `try`/`except` inside `out()`. Every path is already caught for
you, and catching them yourself hides the message you need.

## Python runs at construction, not in the program

Everything inside `out()` executes while the term is being built, in the
host's interpreter. `if`, `for`, `while` and `try` written there decide what
the tree looks like. They are not in the tree and they do not run when the
program runs. Branching and looping that must happen while the program runs
are atoms: `IfDo`, `ForEachDo`, `ForRangeDo`, `WhileDo`, `SwitchDo`.
