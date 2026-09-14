// The chat wire vocabulary.
//
// Three roles, and they are real fields off the store rather than anything
// derived here. `nuspace/chat/shapes.py` writes them:
//
//   user     a person typed it in the composer below.
//   agent    the agent wrote it -- by emitting a program that appended it.
//   system   the host wrote it, about the run rather than about the work.
//            Budget gone, loop crashed. Nothing else.
//
// The middle one is the whole idea of this surface and worth stating plainly:
// nuagent's only output is a Nu term, so the agent has no reply channel. It
// speaks by acting -- appending to `Space.chat.messages` in the program it
// emits, the same primitive it uses to add a page. Which means the model's
// actual reply text, the prose it writes around the fenced block, is NOT here
// and must not be: that is reasoning, and reasoning is not an answer. It lives
// in `Space.agent` and the lens is where you read it.
//
// The consequence for this file: nothing infers an author from position. An
// earlier cut derived "the human's ask" from index zero, because it was
// rendering nuagent's internal transcript where every later user-role message
// was really machine output. That inference is gone with the thing that needed
// it. A message says who wrote it.

export type Role = "user" | "agent" | "system";

export type Message = {
	role: Role;
	text: string;
};

/** What a run is doing. Mirrors `nuspace/agent/shapes.py`. */
export type Status = "idle" | "running" | "done" | "stopped" | "failed";

export type ChatValue = {
	messages: Message[];
	status: Status;
	task: string;
	turns: number;
	error: string;
	/** False until the first frame lands, so "empty" and "not yet" differ. */
	loaded: boolean;
};

export const EMPTY_CHAT: ChatValue = {
	messages: [],
	status: "idle",
	task: "",
	turns: 0,
	error: "",
	loaded: false,
};

const STATUSES = new Set<string>(["idle", "running", "done", "stopped", "failed"]);

/** A status off the wire, or `idle` for anything unrecognised. */
export function coerceStatus(raw: unknown): Status {
	const value = String(raw ?? "");
	return STATUSES.has(value) ? (value as Status) : "idle";
}

const ROLES = new Set<string>(["user", "agent", "system"]);

/**
 * The conversation off the wire.
 *
 * An unknown role reads as `system` rather than being dropped: the store takes
 * whatever a program appends, so a role nobody planned for is a message that
 * still has to be legible. Losing it would be the worse failure.
 */
export function coerceMessages(raw: unknown): Message[] {
	if (!Array.isArray(raw)) return [];
	const out: Message[] = [];
	for (const entry of raw) {
		if (!entry || typeof entry !== "object") continue;
		const record = entry as Record<string, unknown>;
		const role = String(record.role ?? "");
		out.push({
			role: (ROLES.has(role) ? role : "system") as Role,
			text: String(record.text ?? ""),
		});
	}
	return out;
}

/** What the author line says. */
export const ROLE_LABEL: Record<Role, string> = {
	user: "you",
	agent: "agent",
	system: "space",
};

/** Wire status -> the kit's status tones, for the header pill. */
export const STATUS_TONE: Record<Status, "neutral" | "ok" | "info" | "warn" | "danger"> = {
	idle: "neutral",
	running: "info",
	done: "ok",
	stopped: "warn",
	failed: "danger",
};

/** Whether a run is in flight. The one thing the surface branches on. */
export function isRunning(status: Status): boolean {
	return status === "running";
}
