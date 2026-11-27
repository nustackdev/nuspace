// The facts at the top of a cell's menu: what it is, and how it last ran in
// this pane. Read-only, above the actions (./Gutter.tsx).
//
// Mounted only while the menu is open, so only an open menu reads the
// answer (./info.ts). Until it lands the rows are skeletons; the head is
// drawn at once from what the pane already has, the cell's live status.
//
// The last run is the one the status dot reads, so the two always agree. A
// run of an older version than the source is said in words too, not only
// in its tint: it ran something the source no longer says.

import type { Path } from "@nustackdev/ui-core";
import {
	DropdownMenuDetail,
	DropdownMenuDetails,
	DropdownMenuLabel,
	formatAbsolute,
	formatRelativeTime,
	RelativeTime,
	Skeleton,
	StatusDot,
} from "@nustackdev/ui-kit";
import { CELL_STATUS } from "../../design";
import { PlaneIcon } from "../../icon/PlaneIcon";
import { parseIcon } from "../../icon/parse";
import { useCellInfo } from "../../pane/state";
import type { CellState } from "../types";
import type { CellInfo } from "./info";

/** What a cell made from no spec is called. */
const PROGRAM = "Program";

function Head({ info, state }: { info: CellInfo | null; state: CellState }) {
	const token = CELL_STATUS[state];
	const icon = info?.icon ? parseIcon(info.icon) : null;
	return (
		<DropdownMenuLabel className="flex items-center gap-2 text-text-primary">
			{icon ? <PlaneIcon icon={icon} size="sm" /> : null}
			<span className="min-w-0 flex-1 truncate">
				{info ? info.label || PROGRAM : <Skeleton shape="text" className="h-3 w-16" />}
			</span>
			<span className="flex shrink-0 items-center gap-1.5 font-normal text-text-secondary">
				<StatusDot tone={token.tone} pulse={token.transient} />
				{token.label}
			</span>
		</DropdownMenuLabel>
	);
}

function Loading() {
	return (
		<div className="flex flex-col gap-2 px-2 py-1.5" aria-busy="true">
			<Skeleton shape="text" className="h-3 w-40" />
			<Skeleton shape="text" className="h-3 w-32" />
			<Skeleton shape="text" className="h-3 w-36" />
		</div>
	);
}

/** A fixed moment: when it happened, not how long ago. */
function At({ ts }: { ts: number | null }) {
	if (ts === null) return "never";
	return (
		<time dateTime={new Date(ts).toISOString()} className="tabular-nums">
			{formatAbsolute(ts)}
		</time>
	);
}

function Run({ info, error }: { info: CellInfo; error: string | null }) {
	const run = info.run;
	if (!run.id) {
		return <p className="px-2 pb-1.5 text-xs text-text-muted">Not run in this pane yet</p>;
	}
	const stale = run.version < info.version;
	const failed = run.exit === "failed";
	const shown = run.error || error || "";
	return (
		<DropdownMenuDetails>
			<DropdownMenuDetail label="Ran" mono tone={stale ? "warn" : "default"}>
				v{run.version}
				{stale ? <span className="font-display"> · source changed since</span> : null}
			</DropdownMenuDetail>
			<DropdownMenuDetail label="Started">
				{run.startedAt === null ? "not yet" : <RelativeTime ts={run.startedAt} />}
			</DropdownMenuDetail>
			{run.startedAt !== null ? (
				<DropdownMenuDetail label={run.endedAt === null ? "Running" : "Took"} mono>
					{run.endedAt === null ? (
						<RelativeTime ts={run.startedAt} mode="duration" />
					) : (
						formatRelativeTime(run.endedAt - run.startedAt, "duration")
					)}
				</DropdownMenuDetail>
			) : null}
			{run.exit ? (
				<DropdownMenuDetail label="Exit" tone={failed ? "danger" : "default"}>
					{run.exit}
				</DropdownMenuDetail>
			) : null}
			{run.by || run.backend ? (
				<DropdownMenuDetail label="By">
					{[run.by, run.backend].filter(Boolean).join(" on ")}
				</DropdownMenuDetail>
			) : null}
			{shown ? (
				<DropdownMenuDetail label="Error" tone="danger" wrap className="line-clamp-4">
					{shown}
				</DropdownMenuDetail>
			) : null}
		</DropdownMenuDetails>
	);
}

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
			<Head info={info} state={state} />
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
					<Run info={info} error={error} />
				</>
			) : (
				<Loading />
			)}
		</>
	);
}
