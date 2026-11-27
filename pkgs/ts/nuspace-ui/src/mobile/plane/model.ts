// The plane screen's decisions, as plain functions: what a long-press offers,
// where an added cell goes, what the + sheet lists, and how an id reaches the
// clipboard. The screen (./MobilePlane.tsx) and its sheets only draw them.

import { copyText } from "../../core/clipboard";
import { mintId } from "../../core/ids";
import { awaitCreate } from "../../plane/create";
import { slashPackages } from "../../plane/input/slash";
import type { Notify } from "../../plane/ops";
import type { CellSpec, LayoutRow } from "../../plane/types";

/** What a long-press on a cell offers, in sheet order. */
export type CellAction = "restart" | "copy" | "source" | "delete";

/**
 * The actions on a cell: restart, copy its id and view its source on every
 * plane, delete only where the plane can be written, as on desktop's menu.
 */
export function cellActions(editable: boolean): CellAction[] {
	return editable ? ["restart", "copy", "source", "delete"] : ["restart", "copy", "source"];
}

/**
 * The layout with `cell` added at the end of the plane: after the last cell
 * in reading order, a row of its own. Under a strip it is its own row too,
 * never tucked into the strip's last column.
 */
export function appendRows(layout: readonly LayoutRow[], cell: string): LayoutRow[] {
	return [...layout, { kind: "cell", cell }];
}

/**
 * Add a cell made from the Cell named `spec` at the end of the plane, "" for
 * the empty program. The id is minted here, as on desktop, and an id taken is
 * tried once more under a fresh one (../../plane/create.ts). Returns the id.
 */
export function appendCell(notify: Notify, layout: readonly LayoutRow[], spec: string): string {
	const id = mintId("c");
	notify("cell.create", { cell_id: id, name: spec, rows: appendRows(layout, id) });
	awaitCreate(id, () => {
		const again = mintId("c");
		notify("cell.create", { cell_id: again, name: spec, rows: appendRows(layout, again) });
	});
	return id;
}

/** One block of the + sheet: a package's title (none for the top rows), then its sections. */
export type AddGroup = {
	title: string | null;
	sections: { heading: string | null; items: CellSpec[] }[];
};

/**
 * What the + sheet lists: the desktop `/` menu's rows with nothing typed
 * (../../plane/input/slash.ts), the empty program and nuverse's on top, every
 * other package under its title. All open: a phone scrolls, it does not fold.
 */
export function addCellGroups(cellSpecs: CellSpec[]): AddGroup[] {
	return slashPackages("", cellSpecs).map((pkg) => ({
		title: pkg.key === null ? null : pkg.label,
		sections: pkg.sections,
	}));
}

/**
 * `text` onto the clipboard. The async clipboard needs a secure page, and a
 * phone on the tailnet is often on plain http, so the old copy command is the
 * fallback. False when neither would.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
	if (navigator.clipboard && (await copyText(text))) return true;
	try {
		const area = document.createElement("textarea");
		area.value = text;
		area.setAttribute("readonly", "");
		area.style.position = "fixed";
		area.style.opacity = "0";
		document.body.appendChild(area);
		area.select();
		const ok = document.execCommand("copy");
		area.remove();
		return ok;
	} catch {
		return false;
	}
}
