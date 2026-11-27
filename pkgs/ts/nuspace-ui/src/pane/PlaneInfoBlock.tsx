// The facts at the top of a pane's `...` menu: what its plane is, and how it
// runs in this pane. Read-only, above the actions (./PaneMenu.tsx).
//
// Mounted only while the menu is open, so only an open menu reads the
// answer (../plane/info.ts). Until it lands the rows are skeletons; the head
// is drawn at once with the plane's own icon. Its state is the pane's plane
// run, read the way a cell's status reads its cell run.

import type { Path } from "@nustackdev/ui-core";
import { DropdownMenuDetail, DropdownMenuDetails, DropdownMenuLabel } from "@nustackdev/ui-kit";
import { At, InfoHead, InfoLoading, RunDetails } from "../plane/InfoParts";
import { runState } from "../plane/info";
import { usePlaneInfo } from "./state";

/** What a plane made from no spec is called. */
const PLANE = "Plane";

/** The pane's plane's facts, for the top of its menu. */
export function PlaneInfoBlock({ panePath, icon }: { panePath: Path; icon: string }) {
	const info = usePlaneInfo(panePath);
	return (
		<>
			<InfoHead
				icon={icon}
				title={info ? info.label || PLANE : null}
				state={info ? runState(info.run) : null}
			/>
			{info ? (
				<>
					<DropdownMenuDetails>
						<DropdownMenuDetail label="Cells" mono>
							{info.cells}
						</DropdownMenuDetail>
						{info.children > 0 ? (
							<DropdownMenuDetail label="Planes" mono>
								{info.children}
							</DropdownMenuDetail>
						) : null}
						<DropdownMenuDetail label="Edited">
							<At ts={info.modifiedAt} />
						</DropdownMenuDetail>
						<DropdownMenuDetail label="Created">
							<At ts={info.createdAt} />
						</DropdownMenuDetail>
					</DropdownMenuDetails>
					<DropdownMenuLabel>Run</DropdownMenuLabel>
					<RunDetails run={info.run} none="Not running in this pane" />
				</>
			) : (
				<InfoLoading />
			)}
		</>
	);
}
