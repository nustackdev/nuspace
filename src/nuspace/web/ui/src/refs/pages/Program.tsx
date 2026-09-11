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
import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	Button,
	FieldView,
	IconButton,
	Kbd,
	Toggle,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { Check, Code, Copy, RotateCw } from "lucide-react";
import { useCallback, useState } from "react";
import { SectionStatusPill } from "../../components";
import {
	docProgram,
	docProgramBar,
	docProgramDirty,
	docProgramFields,
	docProgramHeadless,
	docProgramPrefix,
	docStatusTrace,
	SECTION_STATUS,
} from "../../design";
import { CodeBox } from "./Code";
import type { ExitDir } from "./ProseRef";
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
	const [copied, setCopied] = useState(false);
	const state: SectionState = status?.state ?? "idle";
	const token = SECTION_STATUS[state];

	const copyPrefix = useCallback(() => {
		navigator.clipboard
			?.writeText(`sections.${blockId}`)
			.then(() => {
				setCopied(true);
				window.setTimeout(() => setCopied(false), 1200);
			})
			.catch(() => {});
	}, [blockId]);

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
		<div className={docProgram}>
			{/* The block's control row. 32px, the kit's default row, so a program
			    block's chrome lines up with every other control in the shell. */}
			<div className={docProgramBar}>
				<SectionStatusPill status={state} />
				<Tooltip>
					<TooltipTrigger asChild>
						<Button variant="ghost" size="sm" onClick={copyPrefix} className={docProgramPrefix}>
							<span className="truncate">sections.{blockId}</span>
							{copied ? <Check className="text-status-ok" /> : <Copy />}
						</Button>
					</TooltipTrigger>
					<TooltipContent side="bottom">
						{copied ? "copied" : "copy this block's mount prefix"}
					</TooltipContent>
				</Tooltip>
				<span className="flex-1" />
				{dirty ? (
					<span className={docProgramDirty}>
						unsaved
						<Kbd>⌘</Kbd>
						<Kbd>↵</Kbd>
					</span>
				) : null}
				<Tooltip>
					<TooltipTrigger asChild>
						<IconButton
							variant="ghost"
							size="sm"
							aria-label="Restart this section"
							onClick={onRestart}
						>
							<RotateCw />
						</IconButton>
					</TooltipTrigger>
					<TooltipContent side="bottom">{token.hint} — restart this section only</TooltipContent>
				</Tooltip>
				<Tooltip>
					<TooltipTrigger asChild>
						<Toggle
							size="sm"
							pressed={editing}
							onPressedChange={onSetEditing}
							aria-label="Edit this block's source"
						>
							<Code />
							code
						</Toggle>
					</TooltipTrigger>
					<TooltipContent side="bottom">
						{editing ? "close the editor" : "edit source"}
					</TooltipContent>
				</Tooltip>
			</div>

			{/* A diagnostic and a traceback are both inline messages with a tone,
			    an icon and a title, which is the kit's `Alert` exactly. The only
			    document-specific part is that the body is preformatted text. */}
			{status?.error ? (
				<Alert tone={token.tone}>
					<AlertIcon />
					<div className="min-w-0 flex-1">
						<AlertTitle>{state === "invalid" ? "does not compile" : "ran and died"}</AlertTitle>
						<AlertDescription className={docStatusTrace}>{status.error}</AlertDescription>
					</div>
				</Alert>
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
				<div className={docProgramFields}>
					{fields.map((f) => (
						<FieldView key={f.path} field={f} />
					))}
				</div>
			) : !editing && !status?.error ? (
				<div className={docProgramHeadless}>no ui refs — this block runs headless</div>
			) : null}
		</div>
	);
}
