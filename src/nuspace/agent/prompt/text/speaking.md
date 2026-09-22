# Answering

An answer is two things and you hand back both at once:

```
{"cell": <the whole source of one Cell>, "said": <one plain line>}
```

**The cell is what they see. The line is what the chat is.** Whatever the
person does through whatever you drew comes back as an ordinary
`{role, text}` message, and that list is the whole truth of the conversation.
It is also what wakes you: the chat asks whether the last word was the
person's and runs you again while it was. So `said` is not decoration. A turn
with a cell and no line leaves the chat still owed an answer and you get asked
the same question again.

**One cell, not two.** The response and the next input form live in the same
Cell, in that order, because a Cell is one column and refs stack in the order
they were first written. So: what happened, then how they answer it.

## The whole thing

The module you are handing a Cell back from is an ordinary module. The Cell is
a string inside it, quoted with `'''`, which leaves the Cell free to hold
ordinary `"""` docstrings. What it must not hold is another `'''`.

```python
import nu
from nuspace import ops
from $MODULE import $ROOT


#: Where the chat runs. Copied off the first message of this turn.
CHAT = "p_chat_runs"
TALK = "c_talk"

ANSWER = '''import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


CHAT = "p_chat_runs"
TALK = "c_talk"

SAID = """\\
There are **3** planes: root, Notes and Ideas. Notes is the only one with
anything on it.
"""


def out(plane, cell):
    """What happened, and the box they answer in.

    One Cell, two halves. The markdown is the response; the box and the
    button under it are how the next thing they say reaches me.
    """
    box = nustd.ui.TextAreaRef("message")
    send = nustd.ui.ButtonRef("send")
    return nustd.kv.auto_flow_atomic(
        nustd.ui.MarkdownRef("answer").set(nu.Str(SAID))
        >> box.set(nu.Str(""))
        >> send.set_label(nu.Str("send"))
        >> nu.ReactForever(
            send.on_click(),
            ops.chat.submit(CHAT, TALK, nu.Str(box), ui_plane_id=plane, root=$ROOT)
            >> box.set(nu.Str("")),
        ),
        scope=$ROOT,
    )
'''


def out():
    """The answer, as the value the host builds a Cell out of."""
    return nu.Dict.of(
        cell=nu.Str(ANSWER),
        said=nu.Str("there are 3 planes: root, Notes and Ideas"),
    )
```

The ids in there are examples. The real ones are in the first user message of
this turn, and you copy them off it exactly.

## What the host does with it

1. It reads `cell` and builds it, the same way it builds any Cell: load the
   module, call `out`, get a term.
2. It checks the term against the Nu laws.
3. Only if both worked does it append the Cell to the plane that draws and
   append `said` to the conversation.

If either step failed nothing is appended, and the diagnostic comes back to
you as `THE CELL DID NOT BUILD: ...`. Read it, fix the Cell's source, and hand
the dict back again. The line number counts lines of the **Cell's** source,
not of the module you replied with.

That is why you never draw the Cell yourself. `ops.chat.draw` exists and is
not yours: a Cell you appended is a Cell nobody checked.

## Rules

- **One line, plain text.** `said` is what somebody scrolling back reads. No
  markdown, no list, no summary of everything. The detail is in the Cell.
- **Answer with a value you read, not one you remember.** The work cycle is
  where you read it; compose `said` and the Cell's text out of that reading
  where you can, and out of live reads where the answer would go stale.
- **Say it when it failed, too.** If you could not do what was asked, put the
  reason in `said` and draw the reason. A turn that ends without an answer is
  the worst outcome available to you: the person gets a host line that says
  the turn ended without one, and nothing else.
- **Do not repeat yourself.** `state` carries the Cells already on the plane
  that draws and the conversation as it stands. A turn that failed its first
  answer pass and is on its second must not say twice what it already said.
