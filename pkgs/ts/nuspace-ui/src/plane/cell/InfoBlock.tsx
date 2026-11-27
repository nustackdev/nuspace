// The facts at the top of a cell's menu: what it is, and how it last ran in
// this pane. Read-only, above the actions (./Gutter.tsx).
//
// Mounted only while the menu is open, so only an open menu reads the
// answer (../info.ts). Until it lands the rows are skeletons; the head is
// drawn at once from what the pane already has, the cell's live status.
//
// The last run is the one the status dot reads, so the two always agree. A
// run of an older version than the source is said in words too, not only
// in its tint: it ran something the source no longer says.

import type { Path } from "@nustackdev/ui-core";
import { DropdownMenuDetail, DropdownMenuDetails, DropdownMenuLabel } from "@nustackdev/ui-kit";
import { useCellInfo } from "../../pane/state";
import { At, InfoHead, InfoLoading, RunDetails } from "../InfoParts";
import type { CellState } from "../types";

/** What a cell made from no spec is called. */
const PROGRAM = "Program";

/** The cell's facts, for the top of its menu. */
export function CellInfoBlock({
	panePath,
	cellId,
	state,
	error,
}: {
	/** The pane node the answer lands on. */
	panePath: Path;
	cellId: string;
	/** Its live status, drawn before the answer lands. */
	state: CellState;
	error: string | null;
}) {
	const info = useCellInfo(panePath, cellId);
	return (
		<>
			<InfoHead icon={info?.icon ?? ""} title={info ? info.label || PROGRAM : null} state={state} />
			{info ? (
				<>
					<DropdownMenuDetails>
						{info.name ? <DropdownMenuDetail label="Name">{info.name}</DropdownMenuDetail> : null}
						<DropdownMenuDetail label="Version" mono>
							v{info.version}
						</DropdownMenuDetail>
						<DropdownMenuDetail label="Edited">
							<At ts={info.modifiedAt} />
						</DropdownMenuDetail>
						<DropdownMenuDetail label="Created">
							<At ts={info.createdAt} />
						</DropdownMenuDetail>
					</DropdownMenuDetails>
					<DropdownMenuLabel>Last run</DropdownMenuLabel>
					<RunDetails
						run={info.run}
						version={info.version}
						error={error}
						none="Not run in this pane yet"
					/>
				</>
			) : (
				<InfoLoading />
			)}
		</>
	);
}
