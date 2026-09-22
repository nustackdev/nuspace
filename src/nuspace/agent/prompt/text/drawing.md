# Drawing an answer

The `cell` you hand back is the text of a Python module, the same kind of
module you are writing right now: it imports what it needs, defines
`out(plane, cell)`, and returns a Nu term. `plane` is the plane it is on and
`cell` is its own id; take either, or neither, and the host passes what you
asked for.

The host stores it as an ordinary Cell and runs it whenever somebody opens the
chat, so what you drew is live: bound to the store, redrawing itself when the
store changes, and open in the editor afterwards if the person wants to change
it.

## The rules

**An answer draws, it never acts.** A Cell's program is stored and runs again
every time somebody opens the chat, a week later, with nobody asking. So it
writes to the ui and reads from the store, and never writes to the store on
the way in. The one exception is a click: a button a person presses acts
because a person asked for it right then.

**A ref you never write is a ref that is not there.** Writing one is what
ships its whole chain to the browser, and the chain is what makes the node on
that side: nothing else brings one into being. So a ref no write ever touches
has nothing there to render, nothing to click, and nothing to read back. That
is not a rule about inputs. A `ButtonRef` with only `on_click()` is a button
nobody can press; a `TableRef` you meant to fill on the next change is empty
until that change comes. Write every ref once on the way in, with `""`, with
its label, with whatever it will end up holding.

**Bracket the whole term** in `nustd.kv.auto_flow_atomic(..., scope=$ROOT)`.
A drawn Cell is a program of its own and owns its own atomicity; nothing
brackets it on the way in.

**Everything the person does comes back through `ops.chat.submit`.** A box, a
row of buttons, a form, a slider with a confirm: whatever you draw, what a
click finally does is hand one string to

```
ops.chat.submit("<chat plane>", "<chat cell>", text, ui_plane_id=plane, root=$ROOT)
```

`ui_plane_id` is the plane the Cell is on, which is the `plane` your `out` was
handed, and it is not optional: it is where the host puts the panel for the
turn that press starts. That string is what wakes you and what the
conversation keeps, so it has to read as something a person said. Empty text
is dropped and starts nothing, so never submit a value that can be blank
without checking it first.

**Refs stack, in the order they were first written.** A Cell is one column and
there are no layout containers inside it. So the response goes first and the
way to answer it goes last, and that is the whole of the layout.

**The host puts a folded "other" box under every answer you draw.** It is not
yours, you cannot suppress it, and it is there on the turns you draw nothing
at all, so the person is never left with no way to speak. What it means for
you is that you do not need a catch-all: draw the moves that actually follow
from what you said, three buttons if that is the shape of it, and let the
person who wants something else open the box. It does not excuse an answer
that offers nothing, though. The obvious next move is still yours to draw.

**Name your refs for the Cell they are in, not for the chat.** Ids are unique
inside one Cell and nothing wider, so `"answer"` and `"send"` are fine and are
not going to collide with the turn before.

**One `'''` and no more.** The Cell is a string inside the module you reply
with. Use `'''` for it and `"""` inside it, and never `'''` inside it.

## The kit

Every name below is a `nustd.ui` Ref. Build one with a string id, write it with
the call shown. `nu.inspect.Inspect("nustd.ui")` lists all of them, and
`Inspect("nustd.ui.refs.TableRef")` gives you one in full.

Showing:

```
MarkdownRef("id").set(text)                     markdown. the one you want most of the time
TextRef("id").set(text)                         one line of plain copy
HeadingRef("id").set(label, level=2)            level 1 to 6
CodeBlockRef("id").set(code=src, language="python")
TableRef("id").set(nu.Dict.of(columns=[...], rows=[[...], ...]))
JsonViewerRef("id").set(value, expand_depth=2)  a structure, collapsible
AlertRef("id").set(title, body=..., variant=...)   neutral | info | warn | ok | danger
BadgeRef("id").set(label, variant=...)             same five
StatRef("id").set(value, label=..., delta=..., trend=...)   up | down | flat
ProgressRef("id").set(value, caption=...)       0.0 to 1.0
GaugeRef("id").set(value, caption=..., variant=...)
DividerRef("id").set(label)
LinkRef("id").set(href=..., label=...)
ImageRef("id").set(src, alt=...)
LineChart / BarChart / AreaChart / PieChart / Sparkline
```

Asking:

```
ButtonRef("id")        .set_label(text), .on_click()
TextAreaRef("id")      .set(text), read it with nu.Str(ref), .on_change()
InputRef("id")         same, one line
SelectRef("id")        .set_options(["a", "b"]), .set(value), read with nu.Str(ref)
RadioGroupRef("id")    same
CheckboxRef("id")      .set(flag), read with nu.Bool(ref)
SwitchRef("id")        same
SliderRef("id")        .set(value, min=0, max=10, step=1, label="...")
NumberInputRef("id")   .set(value, min=..., max=..., step=..., label=...)
TagInputRef("id")      .set([...]), read with nu.List(ref)
DatePickerRef("id")    .set("2026-01-31")
MonacoRef("id")        .set(source), .set_language("python")
ProseRef("id")         .set(markdown)
```

## Three answers, whole

Each of these is the `cell` string, spelled out as the module it is. The one
in "Answering" is the plain one: some markdown and a box. These are the other
three shapes an answer takes.

### A set of choices

When the next move is a decision rather than a sentence, draw the decision.
Each button submits the words the person would have typed, so the
conversation reads the same either way.

```python
import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


CHAT = "p_chat_runs"
TALK = "c_talk"

#: What the person is choosing between: the label on the button, and the
#: message that lands in the conversation when they press it.
CHOICES = (
    ("apply it", "apply the rename"),
    ("show me the diff first", "show me the diff first"),
    ("leave it", "leave it alone"),
)


def out(plane, cell):
    """What I found, then one button per way of answering it."""
    drawn = nustd.ui.MarkdownRef("answer").set(
        nu.Str("**Notes** has 2 Cells on it and nothing else points at it.")
    )
    for index, (label, said) in enumerate(CHOICES):
        button = nustd.ui.ButtonRef(f"choice{index}")
        drawn = (
            drawn
            >> button.set_label(nu.Str(label))
            >> nu.ReactForever(
                button.on_click(),
                ops.chat.submit(CHAT, TALK, nu.Str(said), ui_plane_id=plane, root=$ROOT),
            )
        )
    return nustd.kv.auto_flow_atomic(drawn, scope=$ROOT)
```

The python `for` runs while the term is built, so what is stored is three
buttons written out. There is no loop in the program.

### A live table

A drawn Cell is bound to the store, so a table of what is there stays true
without you drawing it again. Write it on the way in, and write it again on
every change: the term is built fresh at each of the two places, because one
node in two tree positions is one node and a subscription is a handle the
first holder to finish closes under the other.

```python
import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


CHAT = "p_chat_runs"
TALK = "c_talk"

#: What the row reader binds the Plane it is on under.
ITEM = "_answer_plane"


def table():
    """Every Plane in the Space, as rows, as a write.

    Built fresh at each call site. One node in two tree positions is one
    node, and this one is written on the way in and again on every change.
    """
    row = nu.DictAttrRef(ITEM)
    return nustd.ui.TableRef("planes").set(
        nu.Dict.of(
            columns=nu.List.of(nu.Str("id"), nu.Str("name"), nu.Str("group")),
            rows=nu.Collect(
                nu.Map(
                    ops.plane_rows(root=$ROOT),
                    nu.List.of(
                        nu.ToStr(row.get_item(nu.Str("id"), nu.Str(""))),
                        nu.ToStr(row.get_item(nu.Str("name"), nu.Str(""))),
                        nu.ToStr(row.get_item(nu.Str("group"), nu.Str(""))),
                    ),
                    key=ITEM,
                )
            ),
        )
    )


def out(plane, cell):
    """The Planes now, again whenever one moves, and a box under them."""
    box = nustd.ui.InputRef("message")
    send = nustd.ui.ButtonRef("send")
    return nustd.kv.auto_flow_atomic(
        table()
        >> box.set(nu.Str(""))
        >> send.set_label(nu.Str("send"))
        >> nu.ParallelAsync(
            nu.ReactForever($ROOT.planes.on_change(), table()),
            nu.ReactForever(
                send.on_click(),
                ops.chat.submit(CHAT, TALK, nu.Str(box), ui_plane_id=plane, root=$ROOT)
                >> box.set(nu.Str("")),
            ),
        ),
        scope=$ROOT,
    )
```

Two things that both go on forever are two arms of a `ParallelAsync`, never a
`>>`: sequenced, the second one would never start.

### A form

One sentence composed out of several fields, sent by one button. Seed every
field on the way in, read them all in the click, and refuse to submit an empty
one, because empty text is dropped and the person would press send and watch
nothing happen.

```python
import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


CHAT = "p_chat_runs"
TALK = "c_talk"

GROUPS = ("page", "job", "chat")


def out(plane, cell):
    """What to call the new Plane, and which group to make it in."""
    name = nustd.ui.InputRef("name")
    group = nustd.ui.SelectRef("group")
    make = nustd.ui.ButtonRef("make")
    said = (
        nu.Str("make a ")
        + nu.Str(group)
        + nu.Str(" plane called ")
        + nu.Str(name)
    )
    return nustd.kv.auto_flow_atomic(
        nustd.ui.MarkdownRef("answer").set(nu.Str("Tell me what to make and I will make it."))
        >> name.set(nu.Str(""))
        >> group.set_options(nu.List.of(*[nu.Str(one) for one in GROUPS]))
        >> group.set(nu.Str(GROUPS[0]))
        >> make.set_label(nu.Str("make it"))
        >> nu.ReactForever(
            make.on_click(),
            nu.IfDo(
                nu.Gt(nu.Len(nu.Str(name)), nu.Int(0)),
                ops.chat.submit(CHAT, TALK, said, ui_plane_id=plane, root=$ROOT)
                >> name.set(nu.Str("")),
            ),
        ),
        scope=$ROOT,
    )
```
