// The confirm dialog, rendered in jsdom: a question drawn, and each way out
// answering it.

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { confirm } from "./confirm";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

const button = (text: string) =>
	[...document.querySelectorAll("button")].find((b) => b.textContent === text);

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	act(() => root.render(<ConfirmDialog />));
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

function ask(): Promise<boolean> {
	let answer!: Promise<boolean>;
	act(() => {
		answer = confirm({ title: "Delete plane", description: 'Delete "A"?', action: "Delete" });
	});
	return answer;
}

describe("confirm", () => {
	it("draws the question and answers yes on the action", async () => {
		const answer = ask();
		expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Delete "A"?');
		act(() => button("Delete")?.click());
		await expect(answer).resolves.toBe(true);
	});

	it("answers no on cancel, and on a second question", async () => {
		const first = ask();
		const second = ask();
		await expect(first).resolves.toBe(false);
		act(() => button("Cancel")?.click());
		await expect(second).resolves.toBe(false);
	});
});
