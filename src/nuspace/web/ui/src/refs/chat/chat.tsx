// ChatRef -- the agent sidebar.
//
// Pinned on the shell, not on a surface. Nuspace's other three refs mount
// under a Screen and the router decides which one renders; this one mounts as
// a structural slot on the Shell, so `App.tsx` paints it beside whichever
// surface is showing and it never unmounts on navigation. That matters more
// here than anywhere else on the shell: a run outlives the page you started it
// from, and a sidebar that remounted would drop its draft mid-turn.
//
// The wire, both directions, is `nuspace/web/chat/ref.py`:
//
//   server -> browser   {op: "set_chat", messages, status, task, turns, error}
//   browser -> server   `<this ref>.ops.chat.submit` {text}
//                       `<this ref>.ops.chat.reset`  {}
//
// `messages` is `Space.chat` -- what was said -- and NOT the agent run's own
// transcript. The difference is the surface: nuagent emits Nu, not prose, so
// the agent speaks by appending to that slot inside the program it writes. A
// line in this rail is therefore something it *did*, and the rail is subscribed
// to a plain kv list that an app or a cron job can write to just as well.
//
// Every inbound frame carries the whole current answer rather than a delta, so
// a browser that missed one is never left holding a conversation it cannot be
// corrected on.
//
// What the browser owns: the draft you are typing, and whether the rail is
// collapsed. Both are pure interaction state that no other Nu code reads, so
// neither goes near python -- the rule `ui.md` states, and the one the lens
// cursor got wrong once.
//
// Look and feel live in ../../design/chat.ts; the role vocabulary and the
// author derivation live in ./types.ts. Nothing below picks a color or a size.

import { OP_NOTIFY } from "@nustackdev/ui-core";
import type { RefEntry, RefSlice, SliceCtx, SliceFactory } from "@nustackdev/ui-kit";
import {
	Button,
	IconButton,
	Kbd,
	Spinner,
	StatusPill,
	TextArea,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
	useStore,
} from "@nustackdev/ui-kit";
import { Eraser, PanelRightClose, PanelRightOpen, Sparkles } from "lucide-react";
import type React from "react";
import { useCallback, useLayoutEffect, useRef } from "react";

import {
	chatActions,
	chatAsk,
	chatAuthor,
	chatBar,
	chatBarTitle,
	chatCollapsed,
	chatComposer,
	chatEmpty,
	chatError,
	chatHint,
	chatInput,
	chatLog,
	chatMessage,
	chatPending,
	chatReply,
	chatRoot,
	chatSystem,
	chatTurns,
} from "../../design";
import type { Notify, Ops } from "./ops";
import {
	type ChatValue,
	coerceMessages,
	coerceStatus,
	EMPTY_CHAT,
	isRunning,
	type Message,
	ROLE_LABEL,
	STATUS_TONE,
} from "./types";

/* ================================ slice ================================== */

type ChatEditorState = {
	/** What is in the composer right now. Never sent until you submit. */
	draft: string;
	/** Whether the rail is folded to its 36px strip. */
	collapsed: boolean;
};

const EMPTY_EDITOR: ChatEditorState = { draft: "", collapsed: false };

type ChatSlice = RefSlice & { value: ChatValue; editor: ChatEditorState };

const factory: SliceFactory = (path, ctx: SliceCtx) =>
	({
		type: "ChatRef",
		value: { ...EMPTY_CHAT } as ChatValue,
		editor: { ...EMPTY_EDITOR },
		write: (v) =>
			ctx.set((refs) => {
				const slice = refs[path] as ChatSlice | undefined;
				if (!slice) return;
				const p = (v ?? {}) as Record<string, unknown>;
				if (String(p.op ?? "") !== "set_chat") return;
				slice.value = {
					messages: coerceMessages(p.messages),
					status: coerceStatus(p.status),
					task: String(p.task ?? ""),
					turns: Number(p.turns ?? 0),
					error: String(p.error ?? ""),
					loaded: true,
				};
			}),
	}) as ChatSlice;

function useChatValue(path: string): ChatValue {
	return useStore((s) => (s.refs[path]?.value as ChatValue | undefined) ?? EMPTY_CHAT);
}

/** Narrow subscription so a keystroke in the composer does not rerender the log. */
function useChatEditorSlot<T>(path: string, pick: (e: ChatEditorState) => T): T {
	return useStore((s) => pick((s.refs[path] as ChatSlice | undefined)?.editor ?? EMPTY_EDITOR));
}

/**
 * Patch the browser-owned editor state. Module-level rather than a hook so
 * handlers can call it without prop-drilling, and so it never participates in
 * a render.
 */
function patchChatEditor(path: string, patch: Partial<ChatEditorState>): void {
	useStore.setState((s) => {
		const slice = s.refs[path] as ChatSlice | undefined;
		if (!slice) return;
		slice.editor = { ...slice.editor, ...patch };
	});
}

/* ============================== the surface ============================== */

/** One treatment per role. A table, not a chain of ternaries: three peers. */
const BODY: Record<Message["role"], string> = {
	user: chatAsk,
	agent: chatReply,
	system: chatSystem,
};

function MessageView({ message }: { message: Message }) {
	return (
		<div className={chatMessage}>
			<span className={chatAuthor}>{ROLE_LABEL[message.role]}</span>
			<div className={BODY[message.role]}>{message.text}</div>
		</div>
	);
}

function ChatView({ path }: { path: string }) {
	const { messages, status, turns, error, loaded } = useChatValue(path);
	const draft = useChatEditorSlot(path, (e) => e.draft);
	const collapsed = useChatEditorSlot(path, (e) => e.collapsed);
	const send = useStore((s) => s.send);
	const logRef = useRef<HTMLDivElement>(null);

	const running = isRunning(status);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this ref's own wire path, straight off the mount.
	const notify = useCallback<Notify>(
		<K extends keyof Ops>(op: K, args: Ops[K]) => {
			send({ op: OP_NOTIFY, ref: `${path}.ops.${op}`, payload: args });
		},
		[path, send],
	);

	// Pin to the bottom on every new message. Layout effect, not effect: the
	// jump has to happen before paint or a long observation lands visibly and
	// then scrolls away under the reader.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the count is the trigger, not an input -- the body reads only the ref
	useLayoutEffect(() => {
		const node = logRef.current;
		if (node) node.scrollTop = node.scrollHeight;
	}, [messages.length]);

	const submit = useCallback(() => {
		const text = draft.trim();
		if (!text || running) return;
		// The draft is dropped optimistically: the submit appends it to the
		// conversation, which comes straight back as a frame, so keeping it
		// would show the ask twice.
		patchChatEditor(path, { draft: "" });
		notify("chat.submit", { text });
	}, [draft, notify, path, running]);

	// Enter sends, shift+enter breaks the line. The opposite of an editor, and
	// right here: this box is a message, not a document.
	const onKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
			if (e.key !== "Enter" || e.shiftKey) return;
			e.preventDefault();
			submit();
		},
		[submit],
	);

	if (collapsed) {
		return (
			<aside className={chatCollapsed} aria-label="Agent">
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Show the agent"
							onClick={() => patchChatEditor(path, { collapsed: false })}
						>
							<PanelRightOpen />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="left">agent</TooltipContent>
				</Tooltip>
				{running ? <Spinner size="sm" tone="neutral" label="Running" /> : null}
			</aside>
		);
	}

	return (
		<aside className={chatRoot} aria-label="Agent">
			<header className={chatBar}>
				<Sparkles className="size-4 shrink-0 text-text-muted" aria-hidden="true" />
				<span className={chatBarTitle}>agent</span>
				<span className="flex-1" />
				{turns > 0 ? <span className={chatTurns}>{turns}t</span> : null}
				<StatusPill tone={STATUS_TONE[status]} size="sm">
					{status}
				</StatusPill>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Clear the conversation"
							disabled={running || messages.length === 0}
							onClick={() => notify("chat.reset", {})}
						>
							<Eraser />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">clear</TooltipContent>
				</Tooltip>
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Hide the agent"
							onClick={() => patchChatEditor(path, { collapsed: true })}
						>
							<PanelRightClose />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">hide</TooltipContent>
				</Tooltip>
			</header>

			{messages.length === 0 ? (
				<div className={chatEmpty}>
					{loaded ? (
						<>
							<span>nothing asked yet</span>
							<span>tell the agent what to build in this space</span>
						</>
					) : (
						<Spinner size="sm" tone="neutral" label="Connecting" />
					)}
				</div>
			) : (
				<div className={chatLog} ref={logRef}>
					{messages.map((message, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: the conversation is append-only, so position IS the identity
						<MessageView key={`${path}-m-${i}`} message={message} />
					))}
					{error ? <div className={chatError}>{error}</div> : null}
					{running ? (
						<div className={chatPending}>
							<Spinner size="sm" tone="neutral" label="Thinking" />
							thinking...
						</div>
					) : null}
				</div>
			)}

			<div className={chatComposer}>
				<TextArea
					size="sm"
					className={chatInput}
					placeholder={running ? "a run is in flight..." : "ask the agent to do something"}
					aria-label="Ask the agent"
					value={draft}
					disabled={running}
					onChange={(e) => patchChatEditor(path, { draft: e.target.value })}
					onKeyDown={onKeyDown}
				/>
				<div className={chatActions}>
					<span className={chatHint}>
						<Kbd>enter</Kbd> to send
					</span>
					<Button size="sm" disabled={running || draft.trim().length === 0} onClick={submit}>
						send
					</Button>
				</div>
			</div>
		</aside>
	);
}

export const ChatRef: RefEntry = { factory, component: ChatView };
