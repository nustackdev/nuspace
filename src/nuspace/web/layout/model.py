"""The plane layout in plain python: the rows' shape check and the reconcile, and the two hosts running them.

- :func:`rows_problem` (:data:`RowsProblem`): why a list is not a layout,
  ``""`` when it is. What :func:`~.ops.set` checks before it writes.
- :func:`reconcile` (:data:`LayoutReconcile`): a layout kept to the plane's
  cells. It only reconciles: no op logic lives here.

Both pure: new values only, their inputs untouched, no randomness, the same
input the same output.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

from collections.abc import Mapping

import nu
from nuspace.web.strips import fraction, ids, keys_problem, listed, rescaled, shares_problem


__all__ = [
    "KIND_CELL",
    "KIND_STRIP",
    "LayoutReconcile",
    "RowsProblem",
    "reconcile",
    "row_cells",
    "rows_problem",
]


#: The two kinds of row.
KIND_CELL = "cell"
KIND_STRIP = "strip"


# --- The shape ---------------------------------------------------------------------------


def _column_problem(column: object, at: str) -> str:
    said = keys_problem(column, {"cells", "share"}, at)
    if said:
        return said
    cells = column["cells"]  # type: ignore[index]
    if not ids(cells) or not cells or "" in cells:
        return f"{at} cells is not a list of cell ids"
    if not fraction(column["share"]):  # type: ignore[index]
        return f"{at} share is not a number in (0, 1]"
    return ""


def _row_problem(row: object, at: str) -> str:
    if not isinstance(row, Mapping):
        return f"{at} is not a dict"
    kind = row.get("kind")
    if kind == KIND_CELL:
        said = keys_problem(row, {"kind", "cell"}, at)
        if said:
            return said
        cell = row["cell"]
        return "" if isinstance(cell, str) and cell else f"{at} cell is not a cell id"
    if kind == KIND_STRIP:
        said = keys_problem(row, {"kind", "columns"}, at)
        if said:
            return said
        columns = row["columns"]
        if not isinstance(columns, list) or not columns:
            return f"{at} has no columns"
        for c, column in enumerate(columns):
            said = _column_problem(column, f"{at} column {c}")
            if said:
                return said
        return shares_problem(columns, at)
    return f"{at} kind is not {KIND_CELL!r} or {KIND_STRIP!r}"


def rows_problem(rows: object) -> str:
    """Why ``rows`` is not a layout, ``""`` when it is. Plain python, what :data:`RowsProblem` runs.

    A list of rows, each ``{kind: "cell", cell}`` or ``{kind: "strip",
    columns}``, a column ``{cells, share}``: ``cells`` a non-empty list of
    cell ids, ``share`` a number in ``(0, 1]``, a strip's shares summing to
    1. No cell is looked up: which cells are on the plane, a cell in two
    places, a strip left with one cell, are the reconcile's.
    """
    if not isinstance(rows, list):
        return "layout is not a list of rows"
    for r, row in enumerate(rows):
        said = _row_problem(row, f"row {r}")
        if said:
            return said
    return ""


#: ``RowsProblem(rows)``: :func:`rows_problem`.
RowsProblem = nu.host(rows_problem, name="LayoutRowsProblem")


def row_cells(row: Mapping) -> list[str]:
    """The cells a row on the shape holds, in reading order: a strip's column by column."""
    if row["kind"] == KIND_CELL:
        return [row["cell"]]
    return [cell for column in row["columns"] for cell in column["cells"]]


# --- The reconcile -----------------------------------------------------------------------


def _kept(row: Mapping, on_plane: set[str], seen: set[str]) -> dict | None:
    """A new ``row`` holding only its cells on the plane and not ``seen``, ``seen`` taking them. None for none.

    Then the strip rules: an empty column goes, the shares left rescale to
    sum 1, a strip left with one cell becomes a cell row, an empty one goes.
    """
    if row["kind"] == KIND_CELL:
        cell = row["cell"]
        if cell not in on_plane or cell in seen:
            return None
        seen.add(cell)
        return {"kind": KIND_CELL, "cell": cell}
    columns = []
    for column in row["columns"]:
        kept = []
        for cell in column["cells"]:
            if cell in on_plane and cell not in seen:
                seen.add(cell)
                kept.append(cell)
        if kept:
            columns.append({"cells": kept, "share": column["share"]})
    columns = rescaled(columns, len(row["columns"]))
    left = [cell for column in columns for cell in column["cells"]]
    if not left:
        return None
    if len(left) == 1:
        return {"kind": KIND_CELL, "cell": left[0]}
    return {"kind": KIND_STRIP, "columns": columns}


def reconcile(rows: object, cells: object) -> list[dict]:
    """``rows`` kept to ``cells``, the plane's cell ids. Plain python, what :data:`LayoutReconcile` runs.

    - a cell not in ``cells`` (removed, transferred out) is dropped, then the
      strip rules (:func:`_kept`);
    - a cell in two places: the first holder keeps it;
    - a cell in ``cells`` no row holds goes last, as its own cell row, in
      ``cells`` order. An empty layout is every cell its own row;
    - a row off the shape is dropped (its cells then go last).

    Pure: a new list of new rows, ``rows`` and ``cells`` left as they were.
    Cost: O(rows + cells).
    """
    on_plane = [c for c in dict.fromkeys(listed(cells)) if isinstance(c, str)]
    on_set = set(on_plane)
    seen: set[str] = set()
    out: list[dict] = []
    for r, row in enumerate(listed(rows)):
        if _row_problem(row, f"row {r}"):
            continue
        kept = _kept(row, on_set, seen)  # type: ignore[arg-type]
        if kept is not None:
            out.append(kept)
    out.extend({"kind": KIND_CELL, "cell": c} for c in on_plane if c not in seen)
    return out


#: ``LayoutReconcile(rows, cells)``: :func:`reconcile`, what :func:`~.ops.get` and :func:`~.ops.set` run.
LayoutReconcile = nu.host(reconcile, name="LayoutReconcile")
