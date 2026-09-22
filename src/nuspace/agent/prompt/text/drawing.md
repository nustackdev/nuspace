# Drawing a turn

A turn is a Cell. When you finish a reply you put one or more Cells on the
Plane that draws this chat, and the last of them is how the person answers
you back.

```
ops.chat.draw("<the ui plane>", SOURCE, name="answer", root=$ROOT)
```

`SOURCE` is the text of a Python module, the same kind of module you are
writing right now: it imports what it needs, defines `out(plane, cell)`, and
returns a Nu term. The host stores it as an ordinary Cell and runs it
whenever somebody opens the chat, so what you drew is live -- bound to the
store, redrawing itself when the store changes -- and the person can open it
in the editor afterwards and change it.

You write that module as a string inside the program you are emitting. Quote
it with `'''`, which leaves the module free to hold ordinary `"""`
docstrings. What it must not hold is another `'''`, because that ends your
string in the middle of the program.

## The rules

**A turn draws, it never acts.** A Cell's program is stored and runs again
every time somebody opens the chat, a week later, with nobody asking. So a
turn's program writes to the ui and reads from the store, and never writes to
the store on the way in. The one exception is a click: a button a person
presses acts because a person asked for it right then. Acting is what you do
from the Plane you run on, in the program you are writing now.

**Seed every input.** A bare ref exists in the browser from the moment
something writes it. A `TextAreaRef("message")` that nothing writes is a box
nobody can type in: it first appears on the submit that reads it, which is
the one moment it is too late. Write every input once on the way in, even if
only with `""`.

**Bracket the whole term** in `nustd.kv.auto_flow_atomic(..., scope=$ROOT)`.
Every Cell does, including the ones that only draw. A drawn Cell is a program
of its own and owns its own atomicity; nothing brackets it on the way in.

**Everything the person does comes back through `ops.chat.submit`.** A box, a
row of buttons, a form, a slider with a confirm: whatever you draw, what a
click finally does is hand one string to
`ops.chat.submit("<chat plane>", "<chat cell>", text, root=$ROOT)`. That
string is what wakes you and what the conversation keeps, so it has to read
as something a person said. Empty text is dropped and starts nothing, so
never submit a value that can be blank without checking it first.

**Refs stack, in the order they were first written.** A Cell is one column
and there are no layout containers inside it. Two things side by side is two
Cells, not a Row.

**One `draw` is one Cell.** The id is minted while your program is being
built, so a `draw` under a `ForEachDo` or a `ReactForever` would rewrite a
single Cell over and over instead of appending. One call per Cell, written
out.

**Name your refs for the Cell they are in, not for the chat.** Ids are unique
inside one Cell and nothing wider, so `"answer"` and `"send"` are fine and
are not going to collide with the turn before.

## The kit

Every name below is a `nustd.ui` Ref. Build one with a string id, write it
with the call shown. `nu.inspect.Inspect("nustd.ui")` lists all of them, and
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

## Four turns, whole

### A text answer

The one you draw most. Nothing live in it, so nothing subscribes.

```python
import nu
import nustd.kv
import nustd.ui
from $MODULE import $ROOT


SAID = """\
I renamed **Notes** to **Reading**. Nothing else on the plane changed, and
the two Cells on it kept their order.
"""


def out(plane, cell):
    """What just happened, as markdown.

    This whole module is the string a turn's program quoted with `'''`, so
    docstrings like this one are safe in here. Another `'''` would not be.
    """
    return nustd.kv.auto_flow_atomic(
        nustd.ui.MarkdownRef("answer").set(nu.Str(SAID)),
        scope=$ROOT,
    )
```

### A box to answer in

The default next move, and what the chat is seeded with. The box is emptied
after the submit and not before, because the submit is what reads it.

```python
import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from $MODULE import $ROOT


def out(plane, cell):
    """A box to write in and the button that sends it."""
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
```

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
    """The question, and one button per way of answering it."""
    drawn = nustd.ui.TextRef("asked").set(nu.Str("Rename Notes to Reading?"))
    for index, (label, said) in enumerate(CHOICES):
        button = nustd.ui.ButtonRef(f"choice{index}")
        drawn = (
            drawn
            >> button.set_label(nu.Str(label))
            >> nu.ReactForever(
                button.on_click(),
                ops.chat.submit(CHAT, TALK, nu.Str(said), root=$ROOT),
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


#: What the row reader binds the Plane it is on under.
ITEM = "_turn_plane"


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
    """The Planes, now, and again whenever one is added or dropped."""
    return nustd.kv.auto_flow_atomic(
        table() >> nu.ReactForever($ROOT.planes.on_change(), table()),
        scope=$ROOT,
    )
```

A form is the same shape as the choices: draw an `InputRef`, a `SelectRef`
and a `ButtonRef`, seed all three, and have the click compose one sentence
out of what they hold and submit that.
