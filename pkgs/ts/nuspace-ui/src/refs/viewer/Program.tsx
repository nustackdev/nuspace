// A program block's interior: live Nu output, its diagnostic, and its source.
//
// Per block, never per page. v0 had one code/display toggle for the whole
// document, which meant editing anything restarted everything. Here each
// block flips independently, its neighbours keep running, and a save restarts
// exactly one section. That is most of the DX win in this task.
//
// There is no chrome in here. Status, the section id and the code toggle live
// in the gutter (see ./Canvas.tsx), where every block gets them, so what is
// left below is purely what the program produced.
//
// The chrome still consumes the fixed status contract:
//
//   { section_id, state, error, started_at }
//
// How those six states *look* is not decided here -- `../../design` owns the
// vocabulary (hue, silhouette, label, payload well) so the editor never picks
// a token at the call site. `invalid` and `failed` stay distinguishable
// without color: a triangle that never compiled versus a diamond that ran and
// died.

import type { Path } from "@nustackdev/ui-core";
import { Alert, AlertDescription, AlertIcon, AlertTitle, NodeView } from "@nustackdev/ui-kit";
import { useCallback } from "react";
import {
	docProgram,
	docProgramFields,
	docProgramHeadless,
	docStatusTrace,
	SECTION_STATUS,
} from "../../design";
import { useBlockHasUi } from "./blocks";
import { SourceEditor } from "./Code";
import type { FocusReq } from "./state";
import type { ExitDir, SectionState, SectionStatus } from "./types";

export type ProgramProps = {
	source: string;
	/** Where this block's own refs live in the tree. See ./blocks.ts. */
	uiPath: Path;
	status: SectionStatus | null;
	editing: boolean;
	focusReq: FocusReq | null;
	onFocusConsumed: () => void;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	onSelectSelf: () => void;
	onSetEditing: (on: boolean) => void;
};

export function ProgramBlock(props: ProgramProps) {
	const {
		source,
		uiPath,
		status,
		editing,
		focusReq,
		onFocusConsumed,
		onCommit,
		onExit,
		onSelectSelf,
		onSetEditing,
	} = props;

	const hasUi = useBlockHasUi(uiPath);
	const state: SectionState = status?.state ?? "idle";
	const token = SECTION_STATUS[state];

	const leaveEditor = useCallback(() => {
		onSetEditing(false);
		onSelectSelf();
	}, [onSelectSelf, onSetEditing]);

	return (
		<div className={docProgram}>
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
				<SourceEditor
					source={source}
					focusReq={focusReq}
					onFocusConsumed={onFocusConsumed}
					onCommit={onCommit}
					onExit={onExit}
					onEscape={leaveEditor}
				/>
			) : null}

			{hasUi ? (
				<div className={docProgramFields}>
					<NodeView path={uiPath} />
				</div>
			) : !editing && !status?.error ? (
				<div className={docProgramHeadless}>no ui refs, this block runs headless</div>
			) : null}
		</div>
	);
}
