"""The taste app: a nuagent run, wired into the demo space as an app.

What this is
------------

A nuspace **app**: headless, at space lifetime, seeded into
``DemoSpace.apps``. It watches ``DemoSpace.movies``, and every time the
shelf actually changes it hands the shelf to a model, lets that model
write a Nu program, runs the program, and lets the program write the
profile into ``DemoSpace.taste``. The Taste page reads that back.

It is not one call that summarises text. The model is given this app's
Shapes as its surface, it replies with a python module defining ``out()``
returning a Nu term, ``LoadNu`` constructs it, ``Eval`` drives it, and a
module that does not construct comes back as a ``Diagnostic`` for the
model to read on the next turn. The model ends its own run by setting
``Run.done`` in the program that finishes the work.

Why the implementation is sliced out of this file
-------------------------------------------------

The app's stored source is this file, between the two ``APP SOURCE``
markers below. That is deliberate: the source is what a person reads in
the Apps editor, and an app whose source is four lines calling into a
file they cannot see is not a demo of anything. So the whole run -- the
model backend, the prompt, the guards, the transaction, the loop -- is
what gets seeded, verbatim, with one copy on disk rather than two.

It stays real python up here so ruff and the type checker still see it.
The host reads the region back with ``_app_source()``.

``demo_space`` stays an import rather than moving into the region, for
the same reason ``movies_blocks`` exists: a block importing from
``demo.py`` would get a second copy of ``__main__``, and the Shape
classes have to be the *same class objects* the navigator is tagged
with.

What the model is told that the stock prompt does not say
---------------------------------------------------------

``nuagent``'s surface preamble tells a model to **redeclare** the Shapes
it writes against, because ``nu.mem`` addresses by slot name into an
untagged dict and a matching declaration therefore reaches the host's
world. That is exactly wrong here. This space's storage is ``nu.kv``
behind a navigator bound with ``tags=(DemoSpace,)``, so resolution is
keyed on the ``DemoSpace`` *class object*. A redeclared ``DemoSpace``
is a different object, resolves against nothing, and the writes would go
nowhere quietly. So the task tells the model to import the classes
instead, and to redeclare only ``Run``, which is ``nu.mem`` and does work
by name.

Three more, each of which cost a real turn before it was written down:
the model may write ``DemoSpace.taste`` and nothing else (a write to
``movies`` would retrigger the app that is running it); it must not
bracket its own writes, because a transaction is already open around its
program and ``nu.kv`` is not even imported in the module it writes; and
the profile already in ``taste`` is stale by construction, because the
app only runs when the shelf it was written for has changed. Without
that last one the model reads its own previous answer, decides the work
is done, and sets ``Run.done`` without writing anything.
"""

from __future__ import annotations

# Everything between the markers below is what gets stored as the app's
# source, verbatim. Host-only imports live under the END marker.
# --- APP SOURCE START ---
import os
from typing import TYPE_CHECKING

import nuagent
from demo_space import DemoSpace, Movie, Taste

import nu
import nu.kv
import nu.std.time as nutime
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID, UNSET


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu
    from nu.lang.runtime import Runtime


__all__ = [
    "MAX_TURNS",
    "MODEL",
    "TASTE_APP_NAME",
    "TASTE_APP_SOURCE",
    "TASTE_BLOCK_SOURCE",
    "TASTE_INTRO_PROSE",
    "TASTE_PAGE_ID",
    "TASTE_WIRE_PROSE",
    "term",
]


# Sonnet, not Opus. A run is five turns at most and every turn resends the
# whole conversation on top of a ~12k-token system prompt, so the model
# choice is the whole cost of the feature. Overridable, because "is opus
# better at composing a Nu term" is a real question and this is where you
# would answer it.
MODEL = os.environ.get("TASTE_MODEL", "claude-sonnet-4-5")

# Five is two more than the run needs when it goes well: one to look a verb
# up, one to write the program, one spare to fix a diagnostic. The budget
# exists because every logged movie starts a run -- an agent that can spend
# twenty turns on a shelf of five films is a bill, not a feature.
MAX_TURNS = int(os.environ.get("TASTE_MAX_TURNS", "5"))


# --- the model backend ------------------------------------------------------


class Bot(nu.Service):
    """Claude Code prompt surface for one taste run."""

    ask = nu.cc.PromptRef.method()


class FormatMessages(ScalarQuery):
    """Flatten a list of {role, content} dicts into one prompt string.

    Each call to Claude Code is a fresh session, so the whole conversation
    has to ride along in the prompt. Renders as role-tagged blocks. Lifted
    from ``nuagent/examples/tracker.py``; it is the adapter every cc-backed
    agent needs and it is not app-specific.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (msgs,) = children

        def thunk(rt: Runtime) -> object:
            m = msgs(rt)
            if m is EMPTY or m is INVALID:
                return INVALID
            return _render(m)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (msgs,) = children

        async def athunk(rt: Runtime) -> object:
            m = await msgs(rt)
            if m is EMPTY or m is INVALID:
                return INVALID
            return _render(m)

        return athunk


def _render(msgs: list[dict]) -> str:
    parts: list[str] = []
    for d in msgs:
        role = str(d.get("role", "user")).upper()
        content = str(d.get("content", ""))
        parts.append(f"### {role}\n\n{content}")
    return "\n\n".join(parts)


def chat(*, messages: Nu) -> Nu:
    """Adapter matching turn's chat signature. Bot.ask takes prompt=."""
    return Bot.ask(prompt=FormatMessages(messages))


# --- the task ---------------------------------------------------------------


TASK = """\
`DemoSpace.movies` is a shelf of films somebody logged: title, year, genre, a
rating out of ten, whether they watched it, and a line of notes.

**You already have the shelf.** Every observation you are handed carries it in
full under `movies` -- that is what the `state:` line is. Do not spend a turn
returning `DemoSpace.movies` to look at it. (It would not help if you did: a
`ShapesDictRef` reprs as `LazyDictView(container=...)`, so what comes back is the
view, not the films. `DemoSpace.movies.extract()` is the one that yields records.)

Read that shelf and write a taste profile into `DemoSpace.taste`:

- `genres`: the favoured genres, strongest first, comma separated. Use the genre
  values as they appear on the records.
- `tendency`: one short phrase on how this person rates. Generous, harsh, only
  logs what they already like, rates unseen films optimistically -- whatever the
  numbers actually say.
- `prose`: one paragraph of markdown, two or three sentences, addressed to the
  person whose shelf it is. Say what they are drawn to and what they are missing.
  It is a reading, not a table read back as prose.

Write all three in one program, then set `Run.done` in that same program.

**Whatever is already in `taste` is stale.** You are running because the shelf
changed, so the profile in front of you was written for a shelf that no longer
exists. Rewrite all three slots every run. "It already looks right" is not a
reason to skip: the observation shows you `taste` so you can check that your
write landed, not so you can decide the work was already done.

Two rules about *how* you address the world, and they are not negotiable:

1. **Do not redeclare `DemoSpace` or `Taste`.** The general instruction to
   repeat a Shape declaration is for `nu.mem`, which addresses by slot name.
   This app's storage is `nu.kv` behind a navigator tagged with the `DemoSpace`
   class object, so a class you declare yourself is a different address and
   every write you make would land nowhere and raise nothing. Import them:

   ```python
   import nu
   from demo_space import DemoSpace, Taste
   ```

   `Run` is the exception. It is `nu.mem`, it addresses by name, and you
   redeclare it exactly as the surface shows.

2. **Write `DemoSpace.taste` and nothing else.** Not `movies`, not `taste_run`,
   not `state`, not `pages`. An app is watching `movies` for changes and you are
   running inside it; a write there would start another run of you.

3. **Do not bracket your own writes.** No `nu.kv.Transaction`, no `nu.kv.Snapshot`,
   no `nu.kv.auto_flow_atomic`. A write transaction is already open around your
   program and your writes land in it. Wrapping them again costs you the turn --
   the name is not even imported in the module you are writing.

The shelf is in the observation you are given each turn, under `movies`. You do
not have to iterate it in Nu to read it -- the judgement is yours to make. What
has to be a program is the writing.\
"""


def _prompt() -> str:
    """The stock sections plus this app's surface.

    ``DemoSpace`` is on the surface because the model has to address
    ``DemoSpace.taste`` to write anything; ``Movie`` because the shelf
    records in the observation are otherwise untyped blobs; ``Taste``
    because those five slots are the answer. ``TasteRun`` is deliberately
    absent -- it is the machinery that runs the model, not its world.
    """
    sections = nuagent.inserted(
        nuagent.DEFAULT_SECTIONS,
        nuagent.surface_section((DemoSpace, Movie, Taste)),
    )
    return nuagent.system_prompt(TASK, sections=sections)


# --- reads that survive an unset slot ---------------------------------------


def _str(ref: Nu, fallback: str = "") -> Nu:
    """A kv string slot as a Str, tolerating never-written.

    An unset kv slot reads back as a sentinel, not `""`, and a sentinel
    composed into a string collapses the whole term to INVALID -- which
    writes nothing and raises nothing. Every read of a slot the model may
    not have written yet goes through here.
    """
    return nu.Str(nu.If(ref.exists(), nu.ToStr(ref), nu.Str(fallback)))


def state() -> Nu:
    """What the model sees of the world each turn: the shelf, and its own answer so far.

    ``movies.extract()`` rather than ``movies``: a ``ShapesDictRef`` reprs
    as ``LazyDictView(container=...)``, which tells a model nothing at all.
    ``extract`` pulls the records out as a plain dict, and *that* reprs as
    the shelf.
    """
    return nu.Dict.of(
        movies=DemoSpace.movies.extract(),
        taste=nu.Dict.of(
            genres=_str(DemoSpace.taste.genres),
            tendency=_str(DemoSpace.taste.tendency),
            prose=_str(DemoSpace.taste.prose),
        ),
    )


# --- the run ----------------------------------------------------------------


def _agent() -> Nu:
    """One whole agent run as a term. Bindings are hung outside, in :func:`term`.

    The conversation lives on ``MemSession``, bound tagged, so nothing the
    model writes can reach it. ``Run`` rides in the untagged dict, which is
    the same store the model's own redeclaration resolves into -- that is
    how it ends its own run.

    Mem, not ``KVSession``, and that is a choice worth defending. The
    durable thing here is the *profile*, and the profile is on kv. A run's
    conversation is scratch for one shelf change and is thrown away at the
    end of it; there is nothing for a restart to resume, because a restart
    re-reads the shelf and either the fingerprint matches (nothing to do)
    or it does not (start clean). Putting it on kv would also mean binding
    a second navigator tag through the same rocksdb directory, which the
    app tree's ``auto_flow_atomic(scope=DemoSpace)`` pass would then leave
    unbracketed.
    """
    # Two messages, not one, and the second is the whole reason a run is one
    # turn instead of two. `nuagent.agent` appends an observation *after* a
    # program has run, so on the opening turn the model has the task and no
    # world, and it spends that turn writing a program whose only job is to
    # return the shelf. Seeding the first observation by hand -- same "state:"
    # shape the loop appends -- means the shelf is there before the first
    # token, and the model writes the profile immediately. Measured: two turns
    # becomes one.
    seed = nuagent.MemSession.messages.set(
        nu.List.of(
            nu.Dict.of(role="system", content=nu.Str(_prompt())),
            nu.Dict.of(
                role="user",
                content=nu.Str("state: ") + nu.ToStr(nu.Repr(state())),
            ),
        ),
    )
    return nuagent.agent(
        session=nuagent.MemSession,
        chat=chat,
        state=state(),
        max_turns=MAX_TURNS,
        start=seed,
        brace=UNSET,
        echo=True,
    )


def _settled() -> Nu:
    """Land the run somewhere honest, and stamp what the reading was made from.

    ``Run.done`` is the model's own signal that it finished. Read it back
    and the two endings separate: a model that said it was done, and a
    model that ran out of turns. Neither is a crash, so neither is allowed
    to be one.
    """
    landed = (
        DemoSpace.taste.sample.set(nu.Len(DemoSpace.movies))
        >> DemoSpace.taste.computed_at.set(nutime.time())
        >> DemoSpace.taste_run.runs.set(DemoSpace.taste_run.runs + 1)
        >> DemoSpace.taste_run.state.set(nu.Str("ok"))
        >> DemoSpace.taste_run.note.set(nu.Str(""))
    )
    spent = DemoSpace.taste_run.state.set(nu.Str("failed")) >> DemoSpace.taste_run.note.set(
        nu.Str("the model used all ")
        + nu.ToStr(nu.Int(MAX_TURNS))
        + nu.Str(" turns without finishing. The profile above, if there is one, is")
        + nu.Str(" whatever it managed to write before the budget ran out."),
    )
    return (
        DemoSpace.taste_run.turns.set(nu.Int(nuagent.MemSession.turns))
        >> nu.IfDo(nuagent.Run.done, landed, spent)
    )


def _once() -> Nu:
    """One reaction: fingerprint the shelf, run the agent, land somewhere.

    The fingerprint is written *first*, before a single token is spent. A
    kv write fans out more than one change event, the model writes
    ``DemoSpace.taste`` while this is running, and the app is restarted
    whenever its source is edited -- three different ways to arrive back
    here with nothing new to say. Every one of them re-reads the same
    shelf, matches the same fingerprint and does nothing.
    """
    return (
        DemoSpace.taste_run.shelf.set(_digest())
        >> DemoSpace.taste_run.state.set(nu.Str("working"))
        >> DemoSpace.taste_run.note.set(nu.Str("reading the shelf"))
        >> nu.TryCatch(
            # The bracket has to be written by hand, and this is the one
            # thing about the wiring that is not obvious. `auto_flow_atomic`
            # brackets a tree by walking it, and the model's program is not
            # in the tree -- `LoadNu` builds it at run time, so the pass sees
            # an opaque Dynamic subtree, brackets nothing, and the model's
            # first `DemoSpace.taste.genres.set(...)` comes back as
            # "No binding for: SnapshotProtocol[DemoSpace]". A transaction
            # opened here is on the Context when the dynamic program
            # resolves, so the program inherits it.
            #
            # It opens on first use rather than on entry, so nothing is held
            # while the model is thinking: the window is from the model's
            # first write to the end of the loop, which in a run that goes
            # well is the last turn only.
            nu.kv.Transaction(_agent() >> _settled(), scope=DemoSpace),
            # `nu.cc` shells out to Claude Code. Not installed, not logged
            # in, no network: all of it arrives here. An app that let this
            # escape would go `failed` with a traceback as the only signal,
            # and the page would render an empty profile with no
            # explanation next to it.
            catch=DemoSpace.taste_run.state.set(nu.Str("failed"))
            >> DemoSpace.taste_run.note.set(
                nu.Str("could not reach the model: ") + nu.ToStr(nu.AttrRef("error")),
            ),
            errors=Exception,
        )
    )


def _digest() -> Nu:
    """A fingerprint of the shelf: every record, as one string.

    ``Repr`` of the ``ShapesDictRef`` itself is the view's repr and is
    constant no matter what is in it, so this reprs ``extract()`` -- the
    records themselves. Coarse, and it is meant to be: it changes when a
    film is added, removed or edited, and not otherwise.
    """
    return nu.ToStr(nu.Repr(DemoSpace.movies.extract()))


def term(path: str) -> Nu:
    """The whole app: bindings, and a reaction to the shelf under them.

    Args:
        path: this app's kv namespace, ``"apps.<id>"``. Unused -- every
            slot this app touches has a name and a docstring, and an app
            that hid its output under a generated prefix would be an app
            no page could find.

    Returns:
        The app term. Never returns while the space is up.
    """
    del path
    fresh = nu.And(
        # The empty-shelf guard, and it is load bearing on the pass below.
        # A space booted on a fresh store runs this app before anybody has
        # logged anything, and without this the first run of the first boot
        # spends five turns and a real bill reading an empty dict. It is
        # also what makes deleting the last film cheap rather than
        # expensive: the change event fires, the shelf is empty, nothing
        # happens.
        nu.Gt(nu.Len(DemoSpace.movies), nu.Int(0)),
        nu.Ne(_digest(), _str(DemoSpace.taste_run.shelf)),
    )
    return nu.With(
        # The host's working memory, tagged, so the model cannot reach the
        # conversation. `Run` rides in the untagged dict beside it, which
        # is exactly why the model *can* reach that.
        nu.Provide(dict, {}, tag=nuagent.MemSession),
        nu.Provide(dict, {}),
        nu.cc.bind(Bot, model=MODEL, allowed_tools=[], permission_mode="default"),
        body=(
            DemoSpace.taste_run.state.init("idle")
            >> DemoSpace.taste_run.note.init("")
            >> DemoSpace.taste_run.turns.init(0)
            >> DemoSpace.taste_run.runs.init(0)
            # One pass at boot, then react. `on_change` on a kv dict does
            # not fire on mount, and the seed has already run by the time
            # the supervisor starts this app, so without this a space that
            # comes up with a shelf already on it would sit at `idle`
            # forever, waiting for a change that happened before it was
            # listening. The pass is the same guarded body as the
            # reaction, so on the second boot the fingerprint matches and
            # it costs nothing.
            >> nu.IfDo(fresh, _once())
            >> nu.ReactForever(DemoSpace.movies.on_change(), nu.IfDo(fresh, _once()))
        ),
    )


def out(path: str) -> Nu:
    """Entry point. `nu.prog` calls this; `path` is the app's kv namespace."""
    return term(path)


# --- APP SOURCE END ---

import pathlib  # noqa: E402  -- host-only, deliberately below the region
import textwrap  # noqa: E402


# --- what gets seeded -------------------------------------------------------


def _src(text: str) -> str:
    return textwrap.dedent(text).lstrip()


TASTE_APP_NAME = "taste"

_START = "# --- APP SOURCE START ---"
_END = "# --- APP SOURCE END ---"


def _app_source() -> str:
    """This file, between the markers: the app's stored source.

    Read off disk rather than duplicated into a string so there is one
    copy, and so what a person opens in the Apps editor is the code that
    actually ran. The region is self-contained -- it carries its own
    imports and ends with `out(path)`.
    """
    text = pathlib.Path(__file__).read_text()
    body = text.split(_START, 1)[1].split(_END, 1)[0]
    # Prepended rather than sliced: isort keeps a `__future__` import at the
    # top of the file, which is above the marker, and a program needs it for
    # its own reasons -- the type-only names (`Nu`, `Callable`, `Runtime`)
    # are TYPE_CHECKING-only, so their annotations have to stay strings.
    # `nu.prog` compiles with `dont_inherit=True`, so a program gets no
    # future flags it does not ask for itself.
    return "from __future__ import annotations\n" + body.rstrip() + "\n"


TASTE_APP_SOURCE = _app_source()


# --- the page ---------------------------------------------------------------

# Sorts after Control (`p_00_control`) and before the movie pages (`pm_`).
TASTE_PAGE_ID = "p_10_taste"

# This page reads. It does not compute, it does not call a model, and it
# owns no button. Everything on it is a slot the app already wrote, and
# the only logic is "if nothing has been written yet, say so".
TASTE_BLOCK_SOURCE = _src('''
    import nu
    import nu.ui
    import nu.std.time as nutime
    from demo_space import DemoSpace


    TASTE = DemoSpace.taste
    RUN = DemoSpace.taste_run


    def text(ref, fallback):
        # An unset kv slot reads back as a sentinel, not "", and a sentinel
        # in a string collapses the term to INVALID.
        return nu.Str(nu.If(ref.exists(), nu.ToStr(ref), nu.Str(fallback)))


    def out(path):
        state = nu.ui.BadgeRef(path + ".state")
        genres = nu.ui.StatRef(path + ".genres")
        tendency = nu.ui.StatRef(path + ".tendency")
        sample = nu.ui.StatRef(path + ".sample")
        age = nu.ui.StatRef(path + ".age")
        prose = nu.ui.MarkdownRef(path + ".prose")
        note = nu.ui.TextRef(path + ".note")

        here = TASTE.prose.exists()
        run_state = text(RUN.state, "idle")

        # There is no clock in a Nu term without reaching for nu.std.time,
        # and no strftime at all, so "when" is rendered as an age computed
        # at repaint: now, minus the epoch the app stamped.
        seconds = nu.ToInt(nu.Sub(nutime.time(), nu.Float(TASTE.computed_at)))

        def paint():
            return (
                state.set(
                    label=run_state,
                    variant=nu.If(
                        nu.Eq(run_state, nu.Str("ok")),
                        nu.Str("ok"),
                        nu.If(
                            nu.Eq(run_state, nu.Str("failed")),
                            nu.Str("danger"),
                            nu.Str("neutral"),
                        ),
                    ),
                )
                >> genres.set_label(nu.Str("Genres"))
                >> genres.set_value(text(TASTE.genres, "-"))
                >> tendency.set_label(nu.Str("Rates"))
                >> tendency.set_value(text(TASTE.tendency, "-"))
                >> sample.set_label(nu.Str("Read from"))
                >> sample.set_value(
                    nu.If(
                        TASTE.sample.exists(),
                        nu.ToStr(TASTE.sample) + nu.Str(" films"),
                        nu.Str("-"),
                    )
                )
                >> age.set_label(nu.Str("Computed"))
                >> age.set_value(
                    nu.If(
                        TASTE.computed_at.exists(),
                        nu.ToStr(seconds) + nu.Str("s ago"),
                        nu.Str("never"),
                    )
                )
                >> prose.set(
                    nu.If(
                        here,
                        nu.ToStr(TASTE.prose),
                        nu.Str(
                            "_Nothing written yet. Log a movie on **Movies** "
                            "and the app will read the shelf._"
                        ),
                    )
                )
                >> note.set(text(RUN.note, ""))
            )

        return (
            nu.ui.HeadingRef(path + ".h").set(label="Your taste", level=2)
            >> paint()
            # `state` is the last thing every run writes, win or lose, so
            # one subscription repaints the whole card exactly once per
            # outcome. Subscribing to `prose` instead would leave a failed
            # run rendering the previous run's badge.
            >> nu.ReactForever(RUN.state.on_change(), paint())
        )
''')


TASTE_INTRO_PROSE = """# Taste

An agent read the shelf and wrote this. Not a summary of some text: a
`nuagent` run, in an app, at space lifetime.

Log a movie on **Movies** and watch this page. It goes `working` while the
model takes its turns, then `ok` with a rewritten paragraph, or `failed`
with a sentence saying why.
"""

TASTE_WIRE_PROSE = """**What actually happens.** The app watches
`DemoSpace.movies.on_change()`. On a real change it hands the model this
space's own Shapes as its surface, plus the shelf as an observation. The
model replies with a python module defining `out()` that returns a Nu
term; `LoadNu` constructs it, `Eval` runs it, and the term writes
`DemoSpace.taste`. A module that does not construct comes back as a
`Diagnostic` and the model gets another turn to fix its own code. It ends
the run itself by setting `Run.done` in the program that finishes the work.

**What stops it eating itself.** The app fingerprints the shelf and writes
that fingerprint *before* spending a token. A kv write fans out more than
one change event, and the model's own writes land in the same store, so
the app arrives back at the reaction several times per logged movie. Every
one of those re-reads the same shelf, matches the same fingerprint, and
does nothing.

**This page only reads.** One markdown block over slots the app already
wrote, repainting on `taste_run.state`, which is the last thing every run
writes whether it worked or not.
"""
