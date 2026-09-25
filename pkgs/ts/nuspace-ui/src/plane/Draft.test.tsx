// Type to create, rendered in jsdom: a letter in the ghost starts a draft and
// a text cell, and the draft's text lands in the cell's editor once it mounts.
//
// The editor is a stand-in node type drawing a bare contenteditable, and the
// browser's insert is a spy: jsdom edits neither on its own.

import { register, TooltipProvider, tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Plane } from "./Plane";
import type { ActivePlane, Cell, SlashSnippet } from "./types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

register("TestEditor", {
	component: () => <div contentEditable suppressContentEditableWarning tabIndex={-1} />,
});

const VIEWER = ["viewer"];
const SNIPPETS: SlashSnippet[] = [
	{ name: "program", label: "Program" },
	{ name: "prose", label: "Text", onType: true },
];

let host: HTMLDivElement;
let root: Root;
const notify = vi.fn();
const insert = vi.fn(() => true);

function render(cells: Cell[], snippets = SNIPPETS) {
	const plane: ActivePlane = {
		plane_id: "p1",
		title: "",
		meta: { editable: true, full_width: false, compact: false },
		cells,
	};
	act(() => {
		root.render(
			<TooltipProvider>
				<Plane
					viewerPath={VIEWER}
					plane={plane}
					snippets={snippets}
					editable
					wide={false}
					compact={false}
					notify={notify}
				/>
			</TooltipProvider>,
		);
	});
}

function cell(id: string): Cell {
	return {
		id,
		name: "prose",
		source: "",
		status: { cell_id: id, state: "running", error: null, started_at: null },
	};
}

/** Type into a field the way React hears it: native setter, then `input`. */
function typeInto(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
	const proto = Object.getPrototypeOf(el);
	act(() => {
		Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(el, value);
		el.dispatchEvent(new Event("input", { bubbles: true }));
	});
}

const ghost = () => host.querySelector<HTMLInputElement>("input[aria-label='New cell']");
const draftBox = () => host.querySelector<HTMLTextAreaElement>("textarea");

beforeEach(() => {
	tree.getState().write([["viewer"]], {});
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
	notify.mockClear();
	insert.mockClear();
	document.execCommand = insert;
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
	tree.getState().remove(VIEWER);
});

describe("typing into the ghost", () => {
	it("starts a draft and a cell from the flagged snippet, then hands the text off", async () => {
		render([]);
		typeInto(ghost() as HTMLInputElement, "h");

		expect(notify).toHaveBeenCalledTimes(1);
		const [op, args] = notify.mock.calls[0];
		expect(op).toBe("cell.create");
		expect(args).toMatchObject({ plane_id: "p1", name: "prose", index: 0 });
		const box = draftBox() as HTMLTextAreaElement;
		expect(box.value).toBe("h");
		expect(document.activeElement).toBe(box);

		typeInto(box, "hello");
		expect(draftBox()?.value).toBe("hello");

		// The cell arrives with nothing drawn yet: hidden, the draft stays.
		const id = args.cell_id as string;
		render([cell(id)]);
		expect(host.querySelector(`[data-cell="${id}"]`)?.hasAttribute("hidden")).toBe(true);
		expect(draftBox()).not.toBeNull();

		// Its editor mounts with its first value: the text goes in, the draft goes.
		await act(async () => {
			tree.getState().write([["viewer"], ["cells"], [id], ["text", "TestEditor"]], { value: "" });
		});
		expect(insert).toHaveBeenCalledWith("insertText", false, "hello");
		expect(draftBox()).toBeNull();
		const row = host.querySelector(`[data-cell="${id}"]`);
		expect(row?.hasAttribute("hidden")).toBe(false);
		expect(document.activeElement).toBe(row?.querySelector("[contenteditable]"));
	});

	it("opens the / search as before when no snippet is flagged", () => {
		render([], [{ name: "prose", label: "Text" }]);
		typeInto(ghost() as HTMLInputElement, "h");
		expect(notify).not.toHaveBeenCalled();
		expect(draftBox()).toBeNull();
		expect(ghost()?.value).toBe("h");
		expect(ghost()?.placeholder).toBe("Type to search");
	});
});
