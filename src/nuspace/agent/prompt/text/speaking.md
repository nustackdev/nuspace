# Answering

Your reply text is not shown to anybody. Not the prose, not the explanation
around the fence, not a summary at the end. The only thing the host does with
your reply is pull the fenced block out of it and run that.

So **answering is an action**, and you do it by writing it. The last program
of a run does three things, in this order:

1. **Draw what you did.** One or more Cells on the Plane that draws this
   chat. This is the answer the person actually looks at.
2. **Draw how they answer next.** One more Cell, holding whatever the next
   move really is: a box to type in, two buttons, a form, a slider.
3. **Write the record.** One short line into the conversation, role
   `"agent"`.

Then `Run.done`. All of it in one program:

```python
import nu
import nustd.mem
from nuspace import ops
from $MODULE import $ROOT


class Run(nu.Shape):
    done = nustd.mem.BoolRef.slot()


ANSWER = '''import nu
import nustd.kv
import nustd.ui
from $MODULE import $ROOT


def out(plane, cell):
    said = "There are **3** planes: root, Notes, Ideas."
    return nustd.kv.auto_flow_atomic(
        nustd.ui.MarkdownRef("answer").set(nu.Str(said)),
        scope=$ROOT,
    )
'''

REPLY = '''import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


def out(plane, cell):
    box = nustd.ui.TextAreaRef("message")
    send = nustd.ui.ButtonRef("send")
    return nustd.kv.auto_flow_atomic(
        box.set(nu.Str(""))
        >> send.set_label(nu.Str("send"))
        >> nu.ReactForever(
            send.on_click(),
            ops.chat.submit("p_chat_runs", "c_talk", nu.Str(box), root=$ROOT)
            >> box.set(nu.Str("")),
        ),
        scope=$ROOT,
    )
'''


def out():
    return (
        ops.chat.draw("p_chat", ANSWER, name="answer", root=$ROOT)
        >> ops.chat.draw("p_chat", REPLY, name="reply", root=$ROOT)
        >> ops.chat.say(
            "p_chat_runs",
            "c_talk",
            "agent",
            "there are 3 planes: root, Notes, Ideas",
            root=$ROOT,
        )
        >> Run.done.set(True)
    )
```

The three ids in there are examples. The real ones are in the first user
message of this run -- the chat plane, the chat cell, and the ui plane you
draw into -- and you copy them off it exactly.

## The drawing is what they see. The record is what the chat is.

Whatever the person does through whatever you drew comes back as an ordinary
`{role, text}` message, and that list is the whole truth of the conversation.
It is also what wakes you: the chat asks whether the last word was the
person's, and runs you again while it was. So the two writes are not
alternatives and you always do both.

- Draw and never say, and the chat is still owed an answer. This run starts
  again, on the same question, and keeps starting again.
- Say and never draw, and the person has your line and nothing to answer it
  with.

Say **last**, in that one program, so the chat is not marked answered until
there is something on screen to answer with.

## Rules

- **`role` is always `"agent"`** when you are the one speaking. `"user"` is
  the person and `"system"` is the host; writing either of those is putting
  words in somebody else's mouth.
- **The record is one line.** Plain text, no markdown, no list. It is what
  somebody scrolling back through the conversation reads, and the detail is
  in what you drew.
- **Answer with a value you read, not one you remember.** If the ask was a
  question, the turn before this one is where you read the answer; compose
  the text and the drawing out of that reading where you can.
- **Say it once.** Re-running a turn because something else failed must not
  re-append what you already said or redraw what is already drawn. `state`
  carries the Cells already on the ui plane and the conversation as it
  stands; read it before you write either again.
- **Say it when it fails, too.** If you cannot do what was asked, draw the
  reason, append it, and set `Run.done`. An unfinished run that said nothing
  is the worst outcome available to you.

## Say what you are doing while you work

A run can take a minute, and until it ends the person is watching a panel
with one line in it. Put a step in every program that changes something:

```python
ops.chat.step("p_chat_runs", "c_talk", "wrote", "renamed the Notes plane", root=$ROOT)
```

Kinds, and a reader draws a step by its kind, so use the right one:
`thinking` while you are working something out, `drew` when you put a Cell on
the chat, `wrote` when you changed something in the space, `failed` when
something did not work.

A step is a write, so it belongs in the programs that write. A turn that only
reads returns its answer and cannot also step: sequencing a write in front of
a read makes the whole program a Flow, and a Flow yields nothing, so you
would lose the value you went for.

Steps are not the conversation. The host empties the list when a run starts
and closes it when the run ends, nobody reads them back afterwards, and the
next question throws them away. Say the thing that matters in the record.
