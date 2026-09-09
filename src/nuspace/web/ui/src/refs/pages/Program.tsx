// A program block: live Nu output, its supervision status, and its source.
//
// Per block, never per page. v0 had one code/display toggle for the whole
// document, which meant editing anything restarted everything. Here each
// block flips independently, its neighbours keep running, and a save restarts
// exactly one section. That is most of the DX win in this task.
//
// The chrome consumes the fixed status contract:
//
//   { section_id, state, error, started_at }
//
// How those six states *look* is not decided here -- `../../design` owns the
// vocabulary (hue, silhouette, label, payload well) so the editor never picks
// a token at the call site. `invalid` and `failed` stay distinguishable
// without color: a triangle that never compiled versus a diamond that ran and
// died.

import type { MountField } from "@nustackdev/ui-core";
import { FieldView } from "@nustackdev/ui-kit";
import { useCallback, useState } from "react";
import { docStatusPayload, SECTION_STATUS, SectionStatusPill } from "../../design";
import { CodeBox } from "./Code";
import type { ExitDir } from "./Prose";
import type { FocusReq } from "./slice";
import type { SectionState, SectionStatus } from "./types";

export type ProgramProps = {
	blockId: string;
	source: string;
	fields: MountField[];
	status: SectionStatus | null;
	editing: boolean;
	focusReq: FocusReq | null;
	onFocusConsumed: () => void;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	onSelectSelf: () => void;
	onSetEditing: (on: boolean) => void;
	onRestart: () => void;
};

export function ProgramBlock(props: ProgramProps) {
	const {
		blockId,
		source,
		fields,
		status,
		editing,
		focusReq,
		onFocusConsumed,
		onCommit,
		onExit,
		onSelectSelf,
		onSetEditing,
		onRestart,
	} = props;

	const [dirty, setDirty] = useState(false);
	const state: SectionState = status?.state ?? "idle";
	const token = SECTION_STATUS[state];

	const leaveEditor = useCallback(() => {
		onSetEditing(false);
		onSelectSelf();
	}, [onSelectSelf, onSetEditing]);

	const commit = useCallback(
		(next: string) => {
			setDirty(false);
			onCommit(next);
		},
		[onCommit],
	);

	return (
		<div className="flex flex-col gap-1">
			<div className="flex h-8 items-center gap-2">
				<SectionStatusPill status={state} />
				<button
					type="button"
					title="Copy this block's mount prefix"
					onClick={() => navigator.clipboard?.writeText(`sections.${blockId}`).catch(() => {})}
					className="focus-ring truncate rounded-sm font-mono text-xs text-text-muted hover:text-text-secondary"
				>
					sections.{blockId}
				</button>
				<span className="flex-1" />
				{dirty ? <span className="font-mono text-xs text-text-muted">unsaved · ⌘↵</span> : null}
				<button
					type="button"
					onClick={onRestart}
					title={`${token.hint} — restart this section only`}
					className="focus-ring rounded-sm px-1.5 py-0.5 font-mono text-xs text-text-muted hover:bg-doc-hover hover:text-text-primary"
				>
					restart
				</button>
				<button
					type="button"
					onClick={() => onSetEditing(!editing)}
					className={`focus-ring rounded-sm px-1.5 py-0.5 font-mono text-xs ${
						editing
							? "bg-accent text-accent-fg"
							: "text-text-muted hover:bg-doc-hover hover:text-text-primary"
					}`}
				>
					code
				</button>
			</div>

			{status?.error ? (
				<div className={docStatusPayload(state)}>
					<div className="mb-0.5 font-medium">
						{state === "invalid" ? "does not compile" : "ran and died"}
					</div>
					<div className="overflow-x-auto text-text-secondary">{status.error}</div>
				</div>
			) : null}

			{editing ? (
				<CodeBox
					source={source}
					focusReq={focusReq}
					onFocusConsumed={onFocusConsumed}
					onCommit={commit}
					onExit={onExit}
					onEscape={leaveEditor}
					onDirty={setDirty}
				/>
			) : null}

			{fields.length > 0 ? (
				<div className="flex flex-col gap-3 py-1">
					{fields.map((f) => (
						<FieldView key={f.path} field={f} />
					))}
				</div>
			) : !editing && !status?.error ? (
				<div className="py-1 font-mono text-sm text-text-muted">
					no ui refs — this block runs headless
				</div>
			) : null}
		</div>
	);
}
