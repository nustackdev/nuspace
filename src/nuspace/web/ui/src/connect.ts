// WebSocket lifecycle for the nuspace shell.
//
// Mirror of nudle's connect hook, kept local so nuspace ships a standalone
// bundle. Owns: connect, decode inbound frames, backoff-with-jitter reconnect,
// outbound send queue while disconnected, clean teardown.

import { decode, encode, type Frame } from "@nustackdev/ui-core";
import { useStore } from "@nustackdev/ui-kit";
import { useEffect } from "react";

const BACKOFF_BASE_MS = 250;
const BACKOFF_CAP_MS = 10_000;
const SEND_QUEUE_MAX = 64;

function wsUrl(): string {
	const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
	return `${proto}//${window.location.host}/ws`;
}

export function useNuspaceConnection(): void {
	const setStatus = useStore((s) => s.setStatus);
	const setSender = useStore((s) => s.setSender);
	const dispatch = useStore((s) => s.dispatch);

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
		setSender(send);

		const scheduleReconnect = () => {
			if (intentionalClose) return;
			attempts += 1;
			const exp = Math.min(
				BACKOFF_CAP_MS,
				BACKOFF_BASE_MS * 2 ** (attempts - 1),
			);
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
				dispatch(decode(event.data as ArrayBuffer));
			});
		};

		connect();

		return () => {
			intentionalClose = true;
			if (retryTimer !== null) clearTimeout(retryTimer);
			if (ws) ws.close(1000, "client teardown");
		};
	}, [setStatus, setSender, dispatch]);
}
