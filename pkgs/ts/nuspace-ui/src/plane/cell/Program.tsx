// A program cell's interior: live Nu output, its diagnostic, and its source.
//
// Per cell, never per plane. v0 had one code/display toggle for the whole
// document, which meant editing anything restarted everything. Here each
// cell flips independently, its neighbours keep running, and a save restarts
// exactly one cell. That is most of the DX win in this task.
//
// There is no chrome in here. Status, the cell id and the code toggle live
// in the gutter (see ./Gutter.tsx), where every cell gets them, so what is
// left below is purely what the program produced. A cell that draws nothing
// keeps one quiet line, a "No view" chip, on any plane, so it is never an
// invisible gap; an error or an open editor stands in for it.
//
// A cell whose view has not arrived yet is not the same as one that draws
// nothing. The server says per cell whether its program holds ui refs at all
// (`has_ui`). One that does not gets the chip at once. One that does (or an
// older cell that never said) waits: nothing for `VIEW_LOADER_DELAY_MS`, so a
// quick view never flashes a placeholder, then a skeleton until the view
// lands. An error stands in for either.
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
import {
	Alert,
	AlertDescription,
	AlertIcon,
	AlertTitle,
	Badge,
	NodeView,
	Skeleton,
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@nustackdev/ui-kit";
import { useCallback } from "react";
import { useAfter } from "../../core/delay";
import {
	CELL_STATUS,
	docProgram,
	docProgramFields,
	docProgramHeadless,
	docProgramHeadlessChip,
	docProgramLoading,
	docProgramLoadingLine,
	docProgramLoadingLineShort,
	docStatusTrace,
} from "../../design";
import type { FocusReq } from "../state";
import type { CellState, CellStatus, ExitDir } from "../types";
import { useCellHasUi } from "./address";
import { SourceEditor } from "./Code";

/** How long a cell that draws may wait for its view before a skeleton shows. */
export const VIEW_LOADER_DELAY_MS = 1000;

export type ProgramProps = {
	source: string;
	/** Whether the program draws, per the server. Null: it never said. */
	draws: boolean | null;
	/** Where this cell's own refs live in the tree. See ./address.ts. */
	uiPath: Path;
	status: CellStatus | null;
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
		draws,
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

	const hasUi = useCellHasUi(uiPath);
	const state: CellState = status?.state ?? "idle";
	const token = CELL_STATUS[state];
	// No view mounted, nothing else in its place, and one may still come.
	const waiting = !hasUi && !editing && !status?.error && draws !== false;
	const loader = useAfter(waiting, VIEW_LOADER_DELAY_MS);

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
			) : waiting ? (
				loader ? (
					<div className={docProgramLoading} aria-busy="true" data-view-loading="">
						<Skeleton shape="text" className={docProgramLoadingLine} />
						<Skeleton shape="text" className={docProgramLoadingLineShort} />
					</div>
				) : null
			) : !editing && !status?.error ? (
				<div className={docProgramHeadless}>
					<Tooltip>
						<TooltipTrigger asChild>
							<Badge variant="dashed" size="sm" className={docProgramHeadlessChip}>
								No view
							</Badge>
						</TooltipTrigger>
						<TooltipContent side="bottom">This cell draws no ui refs</TooltipContent>
					</Tooltip>
				</div>
			) : null}
		</div>
	);
}
