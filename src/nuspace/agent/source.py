"""The model emits source, the host builds it, and a failure is the next message.

The thesis, and the four Nu terms it needs. There is no tool schema and
nothing to register: a pass is one model call, one python module, one Nu term,
one run. When the module does not build, the diagnostic becomes the next thing
the model reads and it repairs itself. That loop is the whole of the feedback
there is; nothing here judges the work.

nuagent's, brought across and kept as it was, with one thing added.
:func:`stands` is the piece nuagent never needed: a chat's answer is itself
the source of a Cell, and a Cell that will not build is a broken row on the
screen that nobody asked for. So the answer cycle builds it first and only
appends what stood up.

Every one of these is a Nu term rather than a python helper. They evaluate
*inside* the pass, and a python hole in that tree would make it unwalkable and
unrunnable anywhere but the host process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import nu
import nu.prog
from nu.lang.sentinels import UNSET


if TYPE_CHECKING:
    from nu.lang import Nu, StrArg


__all__ = [
    "ANSWER_LABEL",
    "CELL_LABEL",
    "DIAGNOSTICS",
    "ENTRY",
    "FAILED_LABEL",
    "FENCE",
    "NO_CODE",
    "NO_CODE_LABEL",
    "RUNTIME_LABEL",
    "attempted",
    "complaint",
    "diagnostic",
    "failed",
    "fenced",
    "stands",
]


FENCE = "```"

# ```python / ```py / bare ```. The tag heads the chunk, so stripping is a
# chain of removeprefix, each a no-op when it does not match.
_TAGS = ("python", "py")

#: What a Cell's module is asked for. The same entry point the runtime calls
#: when it starts a Cell, so a source that builds here builds there.
ENTRY = "out"

#: Prefix on the diagnostic from a module that did not build.
FAILED_LABEL = "CONSTRUCTION FAILED"

#: Prefix on the diagnostic for a reply that carried no code at all.
NO_CODE_LABEL = "NO CODE BLOCK"

#: Prefix on a program that built and then raised while it ran.
RUNTIME_LABEL = "RUNTIME FAILED"

#: Prefix on a Cell the answer cycle refused to append. A label of its own and
#: not :data:`FAILED_LABEL`, because a pass in the answer cycle has two pieces
#: of source in it and the model has to know which of them is broken: the
#: module it just replied with, or the Cell that module handed back.
CELL_LABEL = "THE CELL DID NOT BUILD"

#: Prefix on an answer cycle pass that ran and handed back something that was
#: not an answer. Its own label for the same reason: the program was fine and
#: what came out of it was not, and those are two different things to fix.
ANSWER_LABEL = "NOT AN ANSWER"

#: Every way a pass ends up carrying a complaint instead of an answer. Matched
#: at the head of the outcome, because that is where each of them is written.
DIAGNOSTICS = (FAILED_LABEL, NO_CODE_LABEL, RUNTIME_LABEL, CELL_LABEL, ANSWER_LABEL)

#: What a model is told when it answered with prose. No line number, because
#: there is no source to have a line 2.
NO_CODE = (
    f"{NO_CODE_LABEL}: your reply contained no fenced code block, so nothing ran. "
    "Prose is not an action here. Reply with one fenced python block defining "
    "out(); to finish the work cycle, send a program that sets Run.done."
)


def fenced(text: StrArg, *, block: Literal["first", "last"] = "first") -> Nu:
    """The source inside a fenced block, as a Str-yielding term.

    Args:
        text: the reply, as a str or any Str-yielding term.
        block: which fenced block to take, ``"first"`` (default) or ``"last"``.

    Returns:
        A ``Str`` term yielding the extracted source.

    Raises:
        ValueError: for a ``block`` other than "first" or "last".

    Notes:
        - Splitting on the fence puts code at the odd indices, so the first
          block is index 1 and the last is the second-to-last chunk, computed
          at runtime because the count is unknown when the tree is built.
        - Neither choice is right always. A model correcting itself quotes the
          broken version first; a model appending an illustration breaks
          last-block. First is the safer default: re-reading broken code costs
          a pass, running an illustration does something nobody asked for.
        - Fewer than three chunks means no complete block, and the whole reply
          is used stripped. That is right for bare source and wrong for prose,
          and the two are not distinguishable here; :func:`failed` resolves it.
    """
    if block not in ("first", "last"):
        msg = f"block must be 'first' or 'last', not {block!r}"
        raise ValueError(msg)

    body = nu.Str(text)
    chunks = body.split(FENCE)
    count = nu.Int(nu.Len(chunks))
    index = nu.Int(1) if block == "first" else count - 2

    picked = nu.Str(nu.List(chunks)[index])
    for tag in _TAGS:
        picked = picked.removeprefix(tag)

    return nu.Str(nu.If(count >= 3, picked.strip(), body.strip()))


def failed(*, reply: Nu | None = None) -> Nu:
    """The catch branch for a module that did not construct: the Diagnostic, as text.

    Args:
        reply: Ref holding the raw model text. Passed, a construction failure
            on a reply with no complete fence reports :data:`NO_CODE` instead.
            Omitted, the Diagnostic is reported either way.

    Returns:
        A ``Str`` term yielding "CONSTRUCTION FAILED: message (line N)", or
        :data:`NO_CODE`.

    Notes:
        - The fenceless fork is what keeps a model from trying to fix its own
          English. Without it, prose reaches the python parser and the model
          is handed "invalid character '-' (U+2014) (line 2)".
    """
    rendered = nu.Str(f"{FAILED_LABEL}: ") + nu.ToStr(diagnostic())
    if reply is None:
        return rendered
    fenceless = nu.Int(nu.Len(nu.Str(reply).split(FENCE))) < 3
    return nu.Str(nu.If(fenceless, nu.Str(NO_CODE), rendered))


def attempted(
    draft: Nu,
    *,
    brace: object = UNSET,
    on_error: Nu | None = None,
    on_crash: Nu | None = None,
) -> Nu:
    """One attempt at the model's program, as text however it goes.

    Args:
        draft: the ``ProgramRef`` holding the source.
        brace: tag of the ``PyBrace`` to construct in.
        on_error: the branch when construction fails. Defaults to :func:`failed`.
        on_crash: the branch when a constructed program raises while running.

    Returns:
        A ``Str`` term: the rendered yield, the Diagnostic, or the runtime
        error, whichever happened.

    Notes:
        - The render sits *inside* the inner ``TryCatch``, not around it.
          Wrapping the whole thing reprs the catch branch, and the model then
          reads its diagnostic quoted with the inner quotes escaped.
        - Both catches exist because a mistake by the model is input, not a
          crash. Source that constructs and then raises is just as much the
          model's error, and uncaught it leaves the pass, leaves the cycle, and
          kills the chat. ``Exception`` is deliberately broad here: everything
          under it comes from evaluating a term the model wrote.
    """
    running = nu.Eval(nu.LoadNu(draft, brace=brace))
    crashed = nu.Str(f"{RUNTIME_LABEL}: ") + nu.ToStr(nu.AttrRef("error"))
    constructed = nu.TryCatch(
        nu.Str(nu.ToStr(nu.Repr(running))),
        catch=failed() if on_error is None else on_error,
        errors=nu.prog.ConstructionError,
    )
    return nu.TryCatch(
        constructed,
        catch=crashed if on_crash is None else on_crash,
        errors=Exception,
    )


def stands(source: StrArg, *, plane_id: nu.StrArg, cell_id: nu.StrArg) -> Nu:
    """Whether ``source`` builds into a Cell that would stand up. Raises if not.

    The answer cycle's guard, and the reason that cycle is a loop of its own.
    A chat's answer is the source of a Cell, and a Cell is only ever built when
    somebody opens the chat, so a model that wrote a broken one would find out
    never and the person would find out by looking at a row that says it
    failed. This builds it first.

    Two checks, and they catch different mistakes. Constructing runs the
    module and calls its entry point, which is every way the source can be
    wrong as python. Validating is what the host does before it drives
    anything, and it is what catches a term that parsed perfectly and puts a
    Command where a value belongs.

    Args:
        source: the Cell's module, as a term or a string.
        plane_id: the Plane the Cell would be on, offered to the entry point.
        cell_id: the id it would have. Both are offered rather than assumed,
            because a Cell's entry point takes them by name and a module that
            asks for something nobody offers is a construction failure.

    Returns:
        A ``Bool`` term yielding True. It never yields False: a source that
        will not stand up raises, so this belongs in the ``cond`` slot of an
        ``IfDo`` whose body is the append, with the raise caught outside it.

    Notes:
        - The rewrite slot is where the check goes, because it is the one hook
          that sees the constructed term and the one place a term cannot be
          obtained having skipped it.
        - What it hands back is a ``Bool`` and not the Cell. The Cell is to be
          stored, not run, and the ``Eval`` above is only here to turn the
          loader's yield into a value the ``cond`` slot can read.
    """
    return nu.Bool(
        nu.Eval(
            nu.LoadNu(
                source,
                entry=ENTRY,
                scope={"plane": plane_id, "cell": cell_id},
                rewrite=_checked,
            )
        )
    )


def complaint(head: nu.Nu) -> nu.Nu:
    """Whether an outcome's first line is one of :data:`DIAGNOSTICS`.

    Read off the text rather than off a slot, because there is no slot: the
    yield of a program that worked and the reason one did not both land in
    ``outcome``, which is right for the model, since either is the same kind
    of thing to read next pass, and leaves the host to tell them apart by the
    label each carries.
    """
    asked = nu.Str(head).startswith(nu.Str(DIAGNOSTICS[0]))
    for label in DIAGNOSTICS[1:]:
        asked = nu.Or(asked, nu.Str(head).startswith(nu.Str(label)))
    return asked


def diagnostic() -> nu.Nu:
    """The Diagnostic off the error a ``TryCatch`` caught.

    Only legal inside a catch branch, which is the one place ``error`` is
    bound, and only for a :class:`~nu.prog.ConstructionError`, which is the
    one error carrying a record rather than just a message.
    """
    return nu.GetAttr(nu.GetAttr(nu.AttrRef("error"), "exception"), "diagnostic")


def _checked(term: nu.Nu) -> nu.Nu:
    """Validate a freshly constructed Cell, then hand back True instead of it."""
    nu.validate(nu.compile(term))
    return nu.Bool(True)
