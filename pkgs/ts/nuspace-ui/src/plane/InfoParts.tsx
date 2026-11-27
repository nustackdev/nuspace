// The pieces a menu's facts are drawn with, a cell's (./cell/InfoBlock.tsx)
// and a plane's (../pane/PlaneInfoBlock.tsx) alike: a head naming what it
// is with its state, skeletons while the answer is on its way, a fixed
// moment, and a run's rows.
//
// When something was made or edited reads as the moment it happened. How a
// run is going reads from now: started "2m ago", running for "1m 12s".

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
import { CELL_STATUS } from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { parseIcon } from "../icon/parse";
import type { RunInfo } from "./info";
import type { CellState } from "./types";

/** The menu's head: an icon, a name (a skeleton while null), and the state as a dot and a word. */
export function InfoHead({
	icon,
	title,
	state,
}: {
	/** Spelled as a plane's icon, "" for none. */
	icon: string;
	title: string | null;
	/** Null while not known: no dot. */
	state: CellState | null;
}) {
	const glyph = icon ? parseIcon(icon) : null;
	const token = state ? CELL_STATUS[state] : null;
	return (
		<DropdownMenuLabel className="flex items-center gap-2 text-text-primary">
			{glyph ? <PlaneIcon icon={glyph} size="sm" /> : null}
			<span className="min-w-0 flex-1 truncate">
				{title ?? <Skeleton shape="text" className="h-3 w-16" />}
			</span>
			{token ? (
				<span className="flex shrink-0 items-center gap-1.5 font-normal text-text-secondary">
					<StatusDot tone={token.tone} pulse={token.transient} />
					{token.label}
				</span>
			) : null}
		</DropdownMenuLabel>
	);
}

export function InfoLoading() {
	return (
		<div className="flex flex-col gap-2 px-2 py-1.5" aria-busy="true">
			<Skeleton shape="text" className="h-3 w-40" />
			<Skeleton shape="text" className="h-3 w-32" />
			<Skeleton shape="text" className="h-3 w-36" />
		</div>
	);
}

/** A fixed moment: when it happened, not how long ago. */
export function At({ ts }: { ts: number | null }) {
	if (ts === null) return "never";
	return (
		<time dateTime={new Date(ts).toISOString()} className="tabular-nums">
			{formatAbsolute(ts)}
		</time>
	);
}

/**
 * A run's rows: when it started, how long it ran, how it ended, who asked
 * and where it ran, and its error. With `version`, the source version the
 * run is checked against: one ran from an older source says so in words.
 */
export function RunDetails({
	run,
	version,
	error,
	none,
}: {
	run: RunInfo;
	/** The source's current version, for a cell's run. Left out for a plane's. */
	version?: number;
	/** An error known besides the run's own, the live status's. */
	error?: string | null;
	/** What shows when there is no run. */
	none: string;
}) {
	if (!run.id) return <p className="px-2 pb-1.5 text-xs text-text-muted">{none}</p>;
	const stale = version !== undefined && run.version < version;
	const shown = run.error || error || "";
	return (
		<DropdownMenuDetails>
			{version !== undefined ? (
				<DropdownMenuDetail label="Ran" mono tone={stale ? "warn" : "default"}>
					v{run.version}
					{stale ? <span className="font-display"> · source changed since</span> : null}
				</DropdownMenuDetail>
			) : null}
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
				<DropdownMenuDetail label="Exit" tone={run.exit === "failed" ? "danger" : "default"}>
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
