// WebSocket lifecycle for the nuspace shell.
//
// Mirror of nudle's connect hook, kept local so nuspace ships a standalone
// bundle. Owns: connect, decode inbound frames, backoff-with-jitter reconnect,
// outbound send queue while disconnected, clean teardown.
//
// The status is browser state and not a node. It is a fact about the socket,
// not about the space, so it has no business in a tree the server writes: a
// reconnect would be the one thing in there nobody on the other end knows
// about. The tree store owns state and dispatch; this owns transport.
//
// Who opens the socket and who reads the status are two different questions,
// so they are two hooks. `useNuspaceConnection` owns the socket and is called
// once, at the top; `useConnectionStatus` is anybody else, and the status
// lives in a module-level store so reading it cannot open a second socket.
// Same shape as ./theme.ts.

import { decode, encode, type Frame } from "@nustackdev/ui-core";
import { tree } from "@nustackdev/ui-kit";
import { useEffect, useSyncExternalStore } from "react";

const BACKOFF_BASE_MS = 250;
const BACKOFF_CAP_MS = 10_000;
const SEND_QUEUE_MAX = 64;

export type Status = "connecting" | "connected" | "disconnected" | "reconnecting";

const subscribers = new Set<() => void>();

let current: Status = "connecting";

function setStatus(status: Status): void {
	if (status === current) return;
	current = status;
	for (const cb of subscribers) cb();
}

function subscribe(cb: () => void): () => void {
	subscribers.add(cb);
	return () => subscribers.delete(cb);
}

function getStatus(): Status {
	return current;
}

/** What the socket is doing right now. Safe anywhere; opens nothing. */
export function useConnectionStatus(): Status {
	return useSyncExternalStore(subscribe, getStatus, getStatus);
}

function wsUrl(): string {
	const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
	return `${proto}//${window.location.host}/ws`;
}

/**
 * Opens `/ws` and wires the tree store's send/dispatch. Call it once, at the
 * top. It returns nothing on purpose: the status goes to whoever draws it
 * through `useConnectionStatus`, so a reconnect does not re-render the shell.
 */
export function useNuspaceConnection(): void {
	useEffect(() => {
		let ws: WebSocket | null = null;
		let attempts = 0;
		let retryTimer: ReturnType<typeof setTimeout> | null = null;
		let intentionalClose = false;
		const queue: Frame[] = [];

		const flushQueue = () => {
			if (!ws || ws.readyState !== WebSocket.OPEN) return;
			while (queue.length > 0) {
				const f = queue.shift();
				if (f) ws.send(encode(f));
			}
		};

		const send = (f: Frame) => {
			if (ws && ws.readyState === WebSocket.OPEN) {
				ws.send(encode(f));
				return;
			}
			queue.push(f);
			if (queue.length > SEND_QUEUE_MAX) queue.shift();
		};
		tree.getState().setSender(send);

		const scheduleReconnect = () => {
			if (intentionalClose) return;
			attempts += 1;
			const exp = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** (attempts - 1));
			const delay = Math.floor(Math.random() * exp);
			setStatus("reconnecting");
			retryTimer = setTimeout(connect, delay);
		};

		const connect = () => {
			retryTimer = null;
			if (intentionalClose) return;
			setStatus(attempts === 0 ? "connecting" : "reconnecting");
			ws = new WebSocket(wsUrl());
			ws.binaryType = "arraybuffer";
			ws.addEventListener("open", () => {
				attempts = 0;
				setStatus("connected");
				flushQueue();
			});
			ws.addEventListener("close", (ev) => {
				if (intentionalClose || ev.code === 1000 || ev.code === 1001) {
					setStatus("disconnected");
					return;
				}
				scheduleReconnect();
			});
			ws.addEventListener("message", (event) => {
				tree.getState().dispatch(decode(event.data as ArrayBuffer));
			});
		};

		connect();

		return () => {
			intentionalClose = true;
			if (retryTimer !== null) clearTimeout(retryTimer);
			tree.getState().setSender(null);
			if (ws) ws.close(1000, "client teardown");
		};
	}, []);
}
