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
// cursor got wrong once. They live in the node's `local` prop, which the wire
// never writes and never reads (see app/local.ts).
//
// No handlers. An inbound frame is a whole answer, so the store's default
// write -- merge the payload object into props -- is exactly right, and the
// coercions that used to run in the slice run at read time in the view
// instead, which is where every ported kit type put them. "Has a frame
// landed" is `messages` being there at all, so `loaded` is not a field
// anybody has to remember to set.
//
// Look and feel live in ../../design/chat.ts; the role vocabulary and the
// author derivation live in ./types.ts. Nothing below picks a color or a size.

import type { Path } from "@nustackdev/ui-core";
import {
	Button,
	IconButton,
	Kbd,
	type NodeEntry,
	type NodeProps,
	pathKey,
	Spinner,
	StatusPill,
	TextArea,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
	useProps,
} from "@nustackdev/ui-kit";
import { Eraser, PanelRightClose, PanelRightOpen, Sparkles } from "lucide-react";
import type React from "react";
import { useCallback, useLayoutEffect, useMemo, useRef } from "react";
import { patchLocal, useLocalSlot } from "../../app/local";
import { notifyOp } from "../../app/wire";
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
import type { Ops } from "./ops";
import {
	type ChatValue,
	coerceMessages,
	coerceStatus,
	isRunning,
	type Message,
	ROLE_LABEL,
	STATUS_TONE,
} from "./types";

/* ============================== local state ============================== */

type ChatEditorState = {
	/** What is in the composer right now. Never sent until you submit. */
	draft: string;
	/** Whether the rail is folded to its 36px strip. */
	collapsed: boolean;
};

const EMPTY_EDITOR: ChatEditorState = { draft: "", collapsed: false };

/** The conversation, read off props and narrowed here rather than on arrival. */
function useChatValue(path: Path): ChatValue {
	const props = useProps(path);
	const raw = props.messages;
	// Memoized on the raw prop, not rebuilt per render: the log below maps
	// over this list and a keystroke in the composer must not re-key it.
	const messages = useMemo(() => coerceMessages(raw), [raw]);
	return {
		messages,
		status: coerceStatus(props.status),
		task: String(props.task ?? ""),
		turns: Number(props.turns ?? 0),
		error: String(props.error ?? ""),
		// A node exists from the moment a chain names it, so existence says
		// nothing. A `messages` key is what only a landed frame can put there.
		loaded: raw !== undefined,
	};
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

function ChatView({ path }: NodeProps) {
	const { messages, status, turns, error, loaded } = useChatValue(path);
	const draft = useLocalSlot(path, EMPTY_EDITOR, (e) => e.draft);
	const collapsed = useLocalSlot(path, EMPTY_EDITOR, (e) => e.collapsed);
	const logRef = useRef<HTMLDivElement>(null);

	const running = isRunning(status);

	// One ref per op: the op name is the tail of the wire path, not a key in
	// the payload. `path` is this node's own address in the tree.
	// biome-ignore lint/correctness/useExhaustiveDependencies: path is compared by value.
	const notify = useCallback(
		<K extends keyof Ops & string>(op: K, args: Ops[K]) => notifyOp<Ops, K>(path, op, args),
		[pathKey(path)],
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
		patchLocal(path, EMPTY_EDITOR, { draft: "" });
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
							onClick={() => patchLocal(path, EMPTY_EDITOR, { collapsed: false })}
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
							onClick={() => patchLocal(path, EMPTY_EDITOR, { collapsed: true })}
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
						<MessageView key={`${pathKey(path)}-m-${i}`} message={message} />
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
					onChange={(e) => patchLocal(path, EMPTY_EDITOR, { draft: e.target.value })}
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

export const ChatRef: NodeEntry = { component: ChatView };
