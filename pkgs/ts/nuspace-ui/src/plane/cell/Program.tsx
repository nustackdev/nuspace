// A program cell's interior: live Nu output, its diagnostic, and its source.
//
// Per cell, never per plane. v0 had one code/display toggle for the whole
// document, which meant editing anything restarted everything. Here each
// cell flips independently, its neighbours keep running, and a save restarts
// exactly one cell. That is most of the DX win in this task.
//
// There is no chrome in here. Status, the cell id and the code toggle live
// in the gutter (see ./Gutter.tsx), where every cell gets them, so what is
// left below is purely what the program produced. On a read-only plane even the
// "runs headless" note goes: the plane draws output and nothing about it.
//
// The chrome still consumes the fixed status contract:
//
//   { cell_id, state, error, started_at }
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
	CELL_STATUS,
	docProgram,
	docProgramFields,
	docProgramHeadless,
	docStatusTrace,
} from "../../design";
import type { FocusReq } from "../state";
import type { CellState, CellStatus, ExitDir } from "../types";
import { useCellHasUi } from "./address";
import { SourceEditor } from "./Code";

export type ProgramProps = {
	source: string;
	/** Where this cell's own refs live in the tree. See ./address.ts. */
	uiPath: Path;
	status: CellStatus | null;
	/** The plane's setting. Off: output only. */
	editable: boolean;
	editing: boolean;
	focusReq: FocusReq | null;
	onFocusConsumed: () => void;
	onCommit: (source: string) => void;
	onExit: (dir: ExitDir, column: number | undefined) => void;
	onSelectSelf: () => void;
	onSetEditing: (on: boolean) => void;
};

export function ProgramCell(props: ProgramProps) {
	const {
		source,
		uiPath,
		status,
		editable,
		editing,
		focusReq,
		onFocusConsumed,
		onCommit,
		onExit,
		onSelectSelf,
		onSetEditing,
	} = props;

	const hasUi = useCellHasUi(uiPath);
	const state: CellState = status?.state ?? "idle";
	const token = CELL_STATUS[state];

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
						<AlertTitle>{state === "invalid" ? "Does not compile" : "Ran and died"}</AlertTitle>
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
				// What the program draws, and what a copy of the cell takes.
				<div className={docProgramFields} data-cell-ui="">
					<NodeView path={uiPath} />
				</div>
			) : editable && !editing && !status?.error ? (
				<div className={docProgramHeadless}>No UI refs, this cell runs headless</div>
			) : null}
		</div>
	);
}
