// The block boundary, which is the part of P3b most likely to break quietly.
//
// The old prose island owned the ProseMirror view, so it could put its
// boundary keys in front of `baseKeymap` as a plugin. Nuspace does not own
// the view any more -- the kit does -- so the same ordering is claimed from
// outside, with a capture-phase listener on a wrapper. That claim is exactly
// the kind of thing that is true until React or ProseMirror changes how it
// attaches listeners, and silently wrong after. So it is pinned here.
//
// jsdom lays nothing out, so `endOfTextblock` and `coordsAtPos` answer
// nonsense and the two vertical-travel bindings cannot be checked here.
// Everything that decides on document structure alone can.

import type { Path } from "@nustackdev/ui-core";
import { tree } from "@nustackdev/ui-kit";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type BlockProse, BlockProseContext, ProseRef } from "./ProseRef";
import { parseMarkdown, serializeMarkdown } from "./prose";

// ---------------------------------------------------------------------------

// React's own flag for "this runner knows about act". Without it every
// render logs a warning that has nothing to do with what is being tested.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const PATH: Path = ["sections", "s_test", "text"];

function bus(over: Partial<BlockProse> = {}): BlockProse {
	return {
		blockId: "s_test",
		focusReq: null,
		slashFrom: null,
		onFocusConsumed: vi.fn(),
		onExit: vi.fn(),
		onMergeUp: vi.fn(),
		onSplit: vi.fn(),
		onSlashOpen: vi.fn(),
		onSlashQuery: vi.fn(),
		onSlashClose: vi.fn(),
		onSlashKey: vi.fn(() => false),
		onSelectSelf: vi.fn(),
		registerHandle: vi.fn(),
		...over,
	};
}

let host: HTMLDivElement;
let root: Root;

/** Mount the entry's component with a value and a bus, like the canvas does. */
async function mount(value: string, b: BlockProse) {
	// One write, chain and all, the way a frame arrives: the two levels above
	// autovivify and the leaf is created with its declared props.
	tree.getState().write([["sections"], ["s_test"], ["text", "ProseRef", { value }]]);
	const Component = ProseRef.component;
	if (!Component) throw new Error("the ProseRef entry has no component");
	await act(async () => {
		root.render(
			<BlockProseContext.Provider value={b}>
				<Component path={PATH} />
			</BlockProseContext.Provider>,
		);
	});
	const editable = host.querySelector<HTMLElement>(".nu-prose-editor");
	if (!editable) throw new Error("the kit editor did not mount");
	return editable;
}

/** One keydown, dispatched the way a browser dispatches one. */
function press(el: HTMLElement, key: string, mods: Partial<KeyboardEventInit> = {}) {
	const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...mods });
	el.dispatchEvent(event);
	return event;
}

beforeEach(() => {
	// The store is a module singleton, so a leftover node from the last case
	// would be the value this one sees.
	tree.getState().remove([]);
	host = document.createElement("div");
	document.body.appendChild(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

// ---------------------------------------------------------------------------

describe("the kit editor mounts and keeps its own job", () => {
	it("renders the markdown as a document, not as source", async () => {
		const editable = await mount("# Title\n\nBody text.\n", bus());
		expect(editable.querySelector("h1")?.textContent).toBe("Title");
		expect(editable.querySelector("p")?.textContent).toBe("Body text.");
		expect(editable.textContent).not.toContain("#");
	});

	it("takes nuspace's recipes, not the kit's defaults", async () => {
		const editable = await mount("# Title\n", bus());
		// docHeading(1). If the dialect ever stops being handed through, this
		// is the assertion that notices.
		expect(editable.querySelector("h1")?.className).toContain("text-3xl");
	});

	it("registers its slash handle with the canvas on mount", async () => {
		const b = bus();
		await mount("hi\n", b);
		expect(b.registerHandle).toHaveBeenCalledWith("s_test", expect.anything());
	});
});

describe("the block boundary, rebuilt on top", () => {
	it("escape hands control back to block selection", async () => {
		const b = bus();
		const editable = await mount("hi\n", b);
		const e = press(editable, "Escape");
		expect(b.onSelectSelf).toHaveBeenCalled();
		expect(e.defaultPrevented).toBe(true);
	});

	it("cmd+enter splits at the caret, head kept and tail handed over", async () => {
		const b = bus();
		const editable = await mount("one\n\ntwo\n", b);
		// Caret at the start of the second paragraph.
		press(editable, "Enter", { metaKey: true });
		expect(b.onSplit).toHaveBeenCalled();
		const [head, tail, insert] = (b.onSplit as ReturnType<typeof vi.fn>).mock.calls[0];
		// Caret defaults to the document start, so everything is the tail.
		expect(head).toBe("");
		expect(tail.trim()).toBe("one\n\ntwo".trim());
		expect(insert).toBe(null);
	});

	it("backspace at the very start merges up and hands over the whole text", async () => {
		const b = bus();
		const editable = await mount("hello\n", b);
		const e = press(editable, "Backspace");
		expect(b.onMergeUp).toHaveBeenCalledWith("hello\n");
		expect(e.defaultPrevented).toBe(true);
	});

	it("a modified arrow never leaves the block", async () => {
		const b = bus();
		const editable = await mount("hi\n", b);
		press(editable, "ArrowUp", { metaKey: true });
		press(editable, "ArrowDown", { shiftKey: true });
		expect(b.onExit).not.toHaveBeenCalled();
	});

	it("a keystroke the block answers never reaches the canvas", async () => {
		const canvas = vi.fn();
		host.addEventListener("keydown", canvas);
		const editable = await mount("hi\n", bus());
		press(editable, "Escape");
		expect(canvas).not.toHaveBeenCalled();
	});
});

describe("the slash menu wins over ProseMirror, which is the ordering claim", () => {
	it("enter picks a menu item instead of splitting the paragraph", async () => {
		const onSlashKey = vi.fn(() => true);
		const b = bus({ slashFrom: 0, onSlashKey });
		const editable = await mount("hello\n", b);
		const before = editable.querySelectorAll("p").length;

		const e = press(editable, "Enter");

		expect(onSlashKey).toHaveBeenCalledWith("Enter");
		expect(e.defaultPrevented).toBe(true);
		// The real assertion: baseKeymap's Enter would have made a second
		// paragraph. Capture phase means it never ran.
		expect(editable.querySelectorAll("p").length).toBe(before);
	});

	it("a key the menu declines falls through to ProseMirror as usual", async () => {
		const b = bus({ slashFrom: 0, onSlashKey: vi.fn(() => false) });
		const editable = await mount("hello\n", b);
		const before = editable.querySelectorAll("p").length;
		press(editable, "Enter");
		expect(editable.querySelectorAll("p").length).toBe(before + 1);
	});
});

describe("the dialect round trips", () => {
	// The schema is nuspace's recipes over the kit's factory, and the parser
	// is the kit's over that schema. The 27 cases live in the kit; this is the
	// one that says the pairing still holds here.
	it.each([
		"# Heading\n",
		"a **bold** and *em* and `code` word\n",
		"- one\n- two\n",
		"1. one\n2. two\n",
		"> quoted\n",
		"---\n",
		"[link](https://example.com)\n",
		"para one\n\npara two\n",
	])("round trips %j", (src) => {
		expect(serializeMarkdown(parseMarkdown(src).doc)).toBe(src);
	});
});
