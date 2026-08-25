// WebSocket lifecycle for the nuspace app. Copied verbatim from nudle.

import { useEffect } from "react";
import { decode, encode, type Frame, OP_MOUNT, type MountField } from "@nustackdev/ui-core";
import { useStore } from "@nustackdev/ui-kit";
import type { NuspaceBlock, NuspaceMount } from "./types";

// The kit's store expects `payload.fields` (+ optional `payload.pages[*].fields`).
// Nuspace's MOUNT payload puts fields under `active_page.blocks[*].fields`.
// Flatten before handing to the store so every field gets a slice.
function adaptMountFrame(frame: Frame): Frame {
	if (frame.op !== OP_MOUNT) return frame;
	const p = frame.payload as NuspaceMount;
	const fields: MountField[] = [];
	if (p?.active_page) {
		for (const b of p.active_page.blocks as NuspaceBlock[]) {
			for (const f of b.fields) fields.push(f);
		}
	}
	return {
		...frame,
		payload: {
			name: "nuspace",
			fields,
			pages: [],
			nuspace: p,
		},
	};
}

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
				dispatch(adaptMountFrame(decode(event.data as ArrayBuffer)));
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
