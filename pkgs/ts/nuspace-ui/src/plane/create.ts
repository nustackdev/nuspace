// A create whose id was taken, tried once more.
//
// The browser mints a new cell's id (../core/ids.ts) and sends it with
// `cell.create`. Two tabs minting the same id is all but impossible, and
// the server refuses the second as `Exists` ("cell <id> exists"), which
// reaches this tab as a toast. A create waiting here hears that toast
// instead of the person: it is sent again, once, under a fresh id. A
// second `Exists` toasts as any refusal does. The wait ends when the cell
// lands (`createLanded`).

/** Creates sent and not landed, by id: what sends each again under a fresh id. */
const waiting = new Map<string, () => void>();

/** `id` was sent; `retry` sends it again under a fresh id should it be taken. */
export function awaitCreate(id: string, retry: () => void): void {
	waiting.set(id, retry);
}

/** `id` landed: nothing more to wait for. */
export function createLanded(id: string): void {
	waiting.delete(id);
}

/** A refusal toast: a create waiting here whose id it names is sent again, and the toast is eaten. */
export function retriedCreate(type: string, message: string): boolean {
	if (type !== "Exists") return false;
	for (const [id, retry] of waiting) {
		if (message !== `cell ${id} exists`) continue;
		waiting.delete(id);
		retry();
		return true;
	}
	return false;
}
