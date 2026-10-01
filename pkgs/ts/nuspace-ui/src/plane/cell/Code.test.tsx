// The source editor in read-only mode, against a stand-in Monaco: the editor
// is built read-only, and nothing it does is ever saved or run.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type Handler = (e?: unknown) => void;
const fake = vi.hoisted(() => ({
	options: null as Record<string, unknown> | null,
	value: "",
	keyDown: null as ((e: unknown) => void) | null,
	blur: null as (() => void) | null,
}));

vi.mock("./monaco", () => {
	const sub = { dispose: () => {} };
	const editor = {
		getValue: () => fake.value,
		setValue: (v: string) => {
			fake.value = v;
		},
		getContentHeight: () => 42,
		layout: () => {},
		getPosition: () => ({ lineNumber: 1, column: 1 }),
		getSelection: () => ({ isEmpty: () => true }),
		getModel: () => ({ getLineCount: () => 1, dispose: () => {} }),
		hasTextFocus: () => false,
		onDidContentSizeChange: () => sub,
		onDidChangeModelContent: () => sub,
		onKeyDown: (h: Handler) => {
			fake.keyDown = h;
			return sub;
		},
		onDidBlurEditorText: (h: () => void) => {
			fake.blur = h;
			return sub;
		},
		dispose: () => {},
	};
	const monaco = {
		KeyCode: { Escape: 9, Enter: 3, UpArrow: 16, DownArrow: 18 },
		editor: {
			create: (_host: unknown, options: Record<string, unknown>) => {
				fake.options = options;
				fake.value = String(options.value);
				return editor;
			},
		},
	};
	return { NU_THEME: "nu", loadMonaco: () => Promise.resolve(monaco) };
});

import { SourceEditor } from "./Code";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

async function mount(readOnly: boolean, onCommit = vi.fn()) {
	const noop = () => {};
	await act(async () => {
		root.render(
			<SourceEditor
				source="x = 1"
				focusReq={null}
				onFocusConsumed={noop}
				onCommit={onCommit}
				onExit={noop}
				onEscape={noop}
				readOnly={readOnly}
			/>,
		);
	});
	return onCommit;
}

const key = (keyCode: number, mod = false) => ({
	keyCode,
	metaKey: mod,
	ctrlKey: false,
	altKey: false,
	shiftKey: false,
	preventDefault: () => {},
	stopPropagation: () => {},
});

describe("a read-only source", () => {
	it("builds Monaco read-only", async () => {
		await mount(true);
		expect(fake.options?.readOnly).toBe(true);
	});

	it("never saves or runs, on blur, mod+enter or Escape", async () => {
		const onCommit = await mount(true);
		fake.value = "x = 2";
		act(() => fake.blur?.());
		act(() => fake.keyDown?.(key(3, true)));
		act(() => fake.keyDown?.(key(9)));
		expect(onCommit).not.toHaveBeenCalled();
	});

	it("an editable one does save on blur", async () => {
		const onCommit = await mount(false);
		expect(fake.options?.readOnly).toBe(false);
		fake.value = "x = 2";
		act(() => fake.blur?.());
		expect(onCommit).toHaveBeenCalledWith("x = 2");
	});
});
