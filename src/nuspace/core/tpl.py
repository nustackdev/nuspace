"""The tpl registry: what a block was made from.

Every block on a page is a Nu program. There is no second substance and
no ``kind`` field asking which one this is. What differs between blocks is
*provenance* -- what produced the source sitting in ``Section.snippet``:

    program   arbitrary. the person wrote it, or pasted it, or a form
              block generated it. nuspace cannot predict what it does.
    text      the wysiwyg template below. the person wrote prose; the
              program that carries it came from here.

``tpl`` is a **hint, not a dispatch**. Nothing branches on it to decide
whether a block compiles, runs, is supervised or reports status -- every
block does all four. Exactly two things read it:

- the editor, to pick an affordance. a text block gets a document
  surface, a program block gets the code toggle, the status pill and the
  mount prefix. that is a rendering choice, not a type test.
- the orchestrator, as a **batching key**. blocks sharing a tpl that is
  not ``arbitrary`` hold byte-identical programs, so N of them can be
  composed into one worker without losing anything. ``SectionSpec.tier``
  carries this up to the supervisor so P4 does not re-derive it.

## Where a block's content lives

An arbitrary tpl has no separate content: the snippet *is* what the
person typed, so it lives in ``Section.snippet`` like it always did.

A template tpl is the other way round. Its snippet is boilerplate, the
same string for every block that shares the tpl, and the thing the person
actually typed is a *value* the template reads. That value lives in
``Space.state[f"sections.<sid>.<slot>"]``.

``Space.state`` rather than a slot on ``Section``, because of the scope
contract. A snippet is a ``nu.prog`` module and nuspace binds it exactly
one value, ``path``, which is ``"sections.<section_id>"``. A slot on
``Section`` would need the *page* path to address -- ``Space.pages.pages
["p_a"].sections["s_b"].text`` -- and ``path`` does not carry it, so the
template could not reach its own content. ``Space.state`` is keyed by
section id alone, which is exactly what ``path`` is. It also keeps
``Section`` from growing a slot per template, and gives any future tpl a
namespace of its own under the same rule.

Nice consequence, and the reason the key and the mount path are the same
string: a text block's content is at ``sections.<sid>.text`` in kv *and*
at ``sections.<sid>.text`` in the browser. One address, both directions.

**Section ids must be globally unique**, not unique per page, and this is
what makes it load bearing. ``mint_ordered_id`` already guarantees it for
anything created through the editor. A hand-written seed that reuses a
readable id on two pages would have the two blocks share one string.


## The store is not migrated

Changing a tpl's template changes what every block made from it runs. The
demo store is disposable, so the answer is to reseed, not to migrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "APP_STARTER",
    "DEFAULT_TPL",
    "TIER_BATCH",
    "TIER_STANDING",
    "TPLS",
    "TPL_PROGRAM",
    "TPL_TEXT",
    "Tpl",
    "app_starter",
    "resolve",
]


TPL_PROGRAM = "program"
TPL_TEXT = "text"
DEFAULT_TPL = TPL_PROGRAM

# Execution tiers. `standing` is one worker per block: arbitrary code, may
# loop forever, needs its own kill ladder. `batch` is "shares a worker with
# its tpl siblings": the program is identical for every block of this tpl,
# so one process can run all of them.
#
# NOTE, because `architecture.md` §8 says otherwise: batch does NOT mean
# "terminates". The text template holds two ReactForevers -- one for the
# browser's edits, one for another connection's -- so it is standing in the
# lifetime sense and batchable in the identity sense. Those turned out to
# be two different properties. P4 owns what to do about it.
TIER_STANDING = "standing"
TIER_BATCH = "batch"


# The wysiwyg template. One `nu.ui.ProseRef` over one string in the space's
# scratch kv, wired both ways:
#
#   kv  -> ref   on boot, and whenever another connection edits the text
#   ref -> kv    whenever this browser commits
#
# `{root}` is the space's own root Shape class, not `Space`. ShapeMeta
# rebinds `_root_shape` on inherited slots, so `Space.state` and
# `DemoSpace.state` are different addresses and only the space's own class
# resolves against its navigator. That is why the template is a format
# string and `source()` takes the root.
_TEXT_TEMPLATE = '''import nu
import nu.kv
import nu.ui
from {module} import {root}


def out(path):
    """One text block: a prose ref over a string in the space's scratch kv."""
    key = path + ".text"
    body = nu.ui.ProseRef(key)
    cell = {root}.state[key]
    # A snippet owns its own atomicity; nothing brackets it on the way in.
    return nu.kv.auto_flow_atomic(
        body.set(nu.ToStr({root}.state.get_item(key, nu.Str(""))))
        >> body.set_placeholder(nu.Str("Write, or press / for blocks"))
        >> nu.ParallelAsync(
            # This browser typed. Persist it; every other connection's copy
            # of this same program hears about it through kv.
            nu.ReactForever(body.changed(), {root}.state.set_item(key, nu.Str(body))),
            # Somebody else typed. Adopt it. A round trip back to the author
            # is a no-op, because the text is already what it says.
            nu.ReactForever(cell.on_change(), body.set(nu.ToStr(cell))),
        ),
        scope={root},
    )
'''


# What a fresh program block starts life as. A block is a `nu.prog` program:
# a python *module* with an `out` entry point returning a Nu term, not a bare
# expression. The entry point's signature is the scope contract and nuspace
# offers one value, `path`, which is this block's own namespace. Seeding the
# skeleton is how that is discoverable without reading docs first.
#
# It lives here rather than in the browser so there is one spelling of it.
_PROGRAM_STARTER = """import nu
import nu.ui


def out(path):
    return nu.ui.TextRef(path + ".out").set(nu.Str("hello"))
"""


# What a fresh app starts life as. An app is the same substance as a block --
# a `nu.prog` module with an `out` entry point, handed one value, `path` --
# and differs in having nowhere to mount a ui ref: it runs headless, whether
# or not a browser is looking. So the starter writes rather than renders.
#
# `{root}` is the space's own root Shape class, for the reason the text
# template gives: ShapeMeta rebinds `_root_shape` on inherited slots, so only
# the space's own class resolves against its navigator.
APP_STARTER = '''import nu
import nu.kv
from {module} import {root}


def out(path):
    """Tick a counter in this app's own corner of the space's scratch kv."""
    key = path + ".ticks"
    now = nu.ToInt({root}.state.get_item(key, nu.Str("0")))
    tick = {root}.state.set_item(key, nu.ToStr(now + nu.Int(1)))
    return nu.kv.auto_flow_atomic(nu.ForeverDo(nu.DelayedDo(1.0, tick)), scope={root})
'''


def app_starter(root: type[Shape]) -> str:
    """The program a new app starts life as, bound to this space's root."""
    return APP_STARTER.format(module=root.__module__, root=root.__name__)


@dataclass(frozen=True)
class Tpl:
    """One template: what it produces, where its content lives, how it runs."""

    name: str
    tier: str
    #: The snippet is whatever the person wrote, so there is no template to
    #: fill and no separate content to store.
    arbitrary: bool
    #: Format string for a non-arbitrary tpl. `{module}` / `{root}` are the
    #: space's root Shape class.
    template: str = ""
    #: Seed for an arbitrary tpl created with no content of its own.
    starter: str = ""
    #: Last segment of the content address, for a non-arbitrary tpl.
    slot: str = "text"

    def source(self, root: type[Shape], content: str = "") -> str:
        """The program this block stores in ``Section.snippet``."""
        if self.arbitrary:
            return content or self.starter
        return self.template.format(module=root.__module__, root=root.__name__)

    def content_key(self, section_id: str) -> str | None:
        """Key under ``Space.state`` holding this block's content.

        ``None`` for an arbitrary tpl, whose content is the snippet.
        Doubles as the browser mount path of the ref that renders it.
        """
        if self.arbitrary:
            return None
        return f"sections.{section_id}.{self.slot}"


PROGRAM = Tpl(
    name=TPL_PROGRAM,
    tier=TIER_STANDING,
    arbitrary=True,
    starter=_PROGRAM_STARTER,
)

TEXT = Tpl(
    name=TPL_TEXT,
    tier=TIER_BATCH,
    arbitrary=False,
    template=_TEXT_TEMPLATE,
    slot="text",
)

TPLS: dict[str, Tpl] = {t.name: t for t in (PROGRAM, TEXT)}


def resolve(name: object) -> Tpl:
    """The tpl called ``name``. Anything unrecognised is a plain program.

    Total on purpose. A blob with no ``tpl`` -- an older store, a block
    written by hand -- is a Nu program, because that is what every block
    is. There is no invalid value to reject.
    """
    return TPLS.get(str(name or ""), PROGRAM)
