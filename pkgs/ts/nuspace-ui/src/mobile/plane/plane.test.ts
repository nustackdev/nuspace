// The plane screen's logic: what a cell's options offer, where Add cell adds
// a cell, and what the add sheet lists.

import { describe, expect, it } from "vitest";
import { retriedCreate } from "../../plane/create";
import { inReadingOrder } from "../../plane/layout/model";
import type { CellSpec, LayoutRow } from "../../plane/types";
import { addCellGroups, appendCell, appendRows, cellActions } from "./model";

const spec = (name: string, label = name): CellSpec => ({ name, label });

describe("cellActions", () => {
	it("offers delete only where the plane can be written", () => {
		expect(cellActions(true)).toEqual(["restart", "copy", "source", "delete"]);
		expect(cellActions(false)).toEqual(["restart", "copy", "source"]);
	});
});

describe("appendRows", () => {
	const strip: LayoutRow = {
		kind: "strip",
		columns: [
			{ share: 0.5, cells: ["b", "c"] },
			{ share: 0.5, cells: ["d"] },
		],
	};

	it("adds the cell as its own last row, after a strip too", () => {
		const rows = appendRows([{ kind: "cell", cell: "a" }, strip], "n");
		expect(rows).toEqual([{ kind: "cell", cell: "a" }, strip, { kind: "cell", cell: "n" }]);
		expect(
			inReadingOrder([{ id: "n" }, { id: "d" }, { id: "a" }, { id: "b" }, { id: "c" }], rows),
		).toEqual(["a", "b", "c", "d", "n"].map((id) => ({ id })));
	});

	it("starts an empty plane", () => {
		expect(appendRows([], "n")).toEqual([{ kind: "cell", cell: "n" }]);
	});
});

describe("appendCell", () => {
	it("sends one create with the cell last, and once more under a fresh id when taken", () => {
		const sent: { op: string; args: { cell_id: string; name: string; rows: LayoutRow[] } }[] = [];
		const notify = ((op: string, args: never) => sent.push({ op, args })) as never;
		const layout: LayoutRow[] = [{ kind: "cell", cell: "a" }];
		const id = appendCell(notify, layout, "nuverse.prose");
		expect(sent).toHaveLength(1);
		expect(sent[0].op).toBe("cell.create");
		expect(sent[0].args).toEqual({
			cell_id: id,
			name: "nuverse.prose",
			rows: [
				{ kind: "cell", cell: "a" },
				{ kind: "cell", cell: id },
			],
		});
		expect(retriedCreate("Exists", `cell ${id} exists`)).toBe(true);
		expect(sent).toHaveLength(2);
		const again = sent[1].args.cell_id;
		expect(again).not.toBe(id);
		expect(sent[1].args.rows.at(-1)).toEqual({ kind: "cell", cell: again });
	});
});

describe("addCellGroups", () => {
	it("lists the empty program first, nuverse untitled, other packages under their titles", () => {
		const groups = addCellGroups([
			spec("nudemos.memes", "Memes"),
			spec("nuverse.prose", "Prose"),
			spec("nuverse.code", "Code"),
		]);
		expect(groups.map((g) => g.title)).toEqual([null, null, "nudemos"]);
		const names = groups.map((g) => g.sections.flatMap((s) => s.items.map((i) => i.name)));
		expect(names).toEqual([[""], ["nuverse.prose", "nuverse.code"], ["nudemos.memes"]]);
	});

	it("keeps the empty program with no registered cells", () => {
		const groups = addCellGroups([]);
		expect(groups.flatMap((g) => g.sections.flatMap((s) => s.items.map((i) => i.label)))).toEqual([
			"Empty",
		]);
	});
});
