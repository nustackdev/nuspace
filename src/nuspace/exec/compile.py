"""Section source -> Nu term, plus the mount fields the term owns.

This runs **in the worker**, never in the server. Compiling a section is
running arbitrary user python, so it happens on the far side of the
process boundary, and the tree it produces stays there -- the worker
that compiles is the worker that runs.

Two authoring shapes are accepted, and they are the same shape:

- an expression (``nu.ui.TextRef(path + '.out').set(...)``), which is
  what v0 sections are;
- a script whose last statement is an expression, or which defines
  ``section()`` / binds ``tree``. A script can do ``class Movie(nu.Shape)``
  and an expression cannot, which is why the script form exists.

Anything else is a diagnostic, not a traceback string.
"""

from __future__ import annotations

import ast
import traceback
from typing import TYPE_CHECKING, Any

import nu
import nu.ui


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["SectionCompileError", "compile_section", "enumerate_ui_refs", "wire_type"]


_REFS_PKG = "nu.ui.refs"


class SectionCompileError(Exception):
    """Source did not produce a Nu tree. Carries a human diagnostic."""

    def __init__(self, message: str, *, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def diagnostic(self) -> str:
        """One line, source-attributed when we know the line."""
        if self.line is None:
            return self.message
        return f"line {self.line}: {self.message}"


def compile_section(source: str, prefix: str) -> tuple[Nu, list[dict[str, Any]]]:
    """Compile ``source`` into a Nu term plus its mount fields.

    ``prefix`` is bound as ``path`` in the snippet scope and is the
    mounting mechanism: every ui ref the snippet names under that prefix
    is a field this section owns.

    Raises:
        SectionCompileError: source is not valid python, blew up while
            building, or did not evaluate to a Nu term.
    """
    filename = f"<section {prefix}>"
    try:
        tree = ast.parse(source, filename=filename, mode="exec")
    except SyntaxError as exc:
        raise SectionCompileError(f"SyntaxError: {exc.msg}", line=exc.lineno) from exc

    scope: dict[str, Any] = {"nu": nu, "path": prefix, "__name__": "__section__"}
    _bind_space(scope)

    tail: ast.Expr | None = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        tail = tree.body.pop()  # type: ignore[assignment]

    try:
        if tree.body:
            exec(compile(tree, filename, "exec"), scope)  # noqa: S102 -- the point
        if tail is not None:
            expr = ast.Expression(body=tail.value)
            ast.copy_location(expr, tail)
            result = eval(compile(expr, filename, "eval"), scope)  # noqa: S307 -- the point
        else:
            result = _from_scope(scope, filename)
    except SectionCompileError:
        raise
    except BaseException as exc:
        raise SectionCompileError(
            f"{type(exc).__name__}: {exc}",
            line=_source_line(exc, filename),
        ) from exc

    if not isinstance(result, nu.Nu):
        raise SectionCompileError(
            f"section returned {type(result).__name__}; expected a Nu term",
        )
    return result, enumerate_ui_refs(result, prefix)


def _from_scope(scope: dict[str, Any], filename: str) -> object:
    """Script form: call ``section()`` or read ``tree``."""
    entry = scope.get("section")
    if callable(entry):
        return entry()
    if "tree" in scope:
        return scope["tree"]
    raise SectionCompileError(
        "source produced no tree; end with an expression, define `section()`, or bind `tree`",
    )


def _bind_space(scope: dict[str, Any]) -> None:
    """Expose ``Space`` when nuspace's shapes are importable."""
    try:
        from nuspace.core.shapes import Space
    except Exception:
        return
    scope["Space"] = Space


def _source_line(exc: BaseException, filename: str) -> int | None:
    """Innermost line number inside the section's own source."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == filename:
            return frame.lineno
    return None


def wire_type(ref_cls: type) -> str:
    """Browser-side factory name for a ui Ref class.

    Same rule the shell uses: an explicit ``_wire_type_override`` wins,
    otherwise the closest ancestor defined inside ``nu.ui.refs``.
    Reimplemented here rather than imported so the worker does not drag
    in the web server package.
    """
    for base in ref_cls.__mro__:
        override = base.__dict__.get("_wire_type_override")
        if isinstance(override, str):
            return override
        module = getattr(base, "__module__", "")
        if module.startswith(_REFS_PKG) and module != _REFS_PKG:
            return base.__name__
    return ref_cls.__name__


def enumerate_ui_refs(term: Nu, prefix: str) -> list[dict[str, Any]]:
    """Mount fields for every ui Ref the term *owns*, deduplicated.

    Path is the mounting mechanism. A snippet may name a ref belonging to
    another section to read it or write into it; that is a live wire and
    it keeps working. But only the section that names a path under its own
    prefix mounts it, so a borrowed ref renders once, in its owner.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict[str, Any]] = []
    own = prefix + "."

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
            if isinstance(segment, str) and (segment == prefix or segment.startswith(own)):
                kind = wire_type(type(node))
                key = (kind, segment)
                if key not in seen:
                    seen.add(key)
                    entry: dict[str, Any] = {"path": segment, "type": kind}
                    props = type(node)._mount_props()
                    if props:
                        entry["props"] = dict(props)
                    fields.append(entry)
        children = getattr(node, "_children", None)
        if children:
            for child in children:
                visit(child)

    visit(term)
    return fields
