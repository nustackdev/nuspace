// The Specs section's body, under the Planes: what the installed
// packages offer, one folding group per package, its registered Planes under
// it. Not planes: a row here is a kind of plane, and clicking it makes a new
// one from it at the top of the tree and opens it, the same as picking it in
// the Add plane popup. The plane it makes is then an ordinary plane, in
// Planes. Hidden when no package registers a Plane.
//
// A registered Plane is named `<package>.<name>` (nuspace.ext), which is what
// groups it. Groups keep the registry's order, packages by entry point. A
// group is folded until opened; its fold state lives with the tree's, under
// `ext:<package>`, so it never meets a plane id.
//
// A group row is a tree row (./SidebarRow.tsx): a package icon at rest
// that turns into the fold chevron on hover. But a package is nothing to
// open, so the whole row is one button: a click anywhere on it, Enter or
// Space folds and unfolds it, and so do the arrows. An entry row makes its
// plane with a click anywhere on it, Enter or Space, and its description
// shows in a tooltip off the sidebar's right edge.

import { Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { ChevronRight, Package } from "lucide-react";
import { openPlane } from "../core/router";
import { sidebarIcon, sidebarLaneChevron, sidebarTooltipWide } from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { createPlane } from "./add";
import { useSidebarNav } from "./focus";
import type { Notify } from "./ops";
import { SidebarRow } from "./SidebarRow";
import type { Registered } from "./types";

/** One package's group: its name, and the Planes it registers, in order. */
export type SpecGroup = { pkg: string; entries: Registered[] };

/** The fold key of a package's group, apart from every plane id. */
export const groupKey = (pkg: string) => `ext:${pkg}`;

/** The package a registered Plane's name belongs to, "" for none. */
export function packageOf(name: string): string {
	const dot = name.indexOf(".");
	return dot > 0 ? name.slice(0, dot) : "";
}

/** The registered Planes by package, packages in the order they first show. */
export function specGroups(registered: Registered[]): SpecGroup[] {
	const by = new Map<string, Registered[]>();
	for (const entry of registered) {
		const pkg = packageOf(entry.name);
		if (!pkg) continue;
		const list = by.get(pkg) ?? [];
		list.push(entry);
		by.set(pkg, list);
	}
	return [...by.entries()].map(([pkg, entries]) => ({ pkg, entries }));
}

/** One visible line of the section: a group, or an entry under an open one. */
export type SpecLine = { key: string; group: SpecGroup; entry?: Registered };

/** The section's visible lines, in order: each group, then its entries while it is open. */
export function specLines(groups: SpecGroup[], expanded: Set<string>): SpecLine[] {
	const out: SpecLine[] = [];
	for (const group of groups) {
		const gKey = groupKey(group.pkg);
		out.push({ key: gKey, group });
		if (expanded.has(gKey))
			for (const entry of group.entries) out.push({ key: `${gKey}/${entry.name}`, group, entry });
	}
	return out;
}

export function Specs({
	groups,
	lines,
	expanded,
	onToggle,
	notify,
}: {
	groups: SpecGroup[];
	/** `specLines` of `groups`, worked out once in ./Sidebar.tsx for the body's focus order. */
	lines: SpecLine[];
	expanded: Set<string>;
	onToggle: (key: string) => void;
	notify: Notify;
}) {
	const { focusKey } = useSidebarNav();
	const make = (entry: Registered) => openPlane(createPlane(notify, entry));

	return lines.map(({ key, group, entry }) => {
		const gKey = groupKey(group.pkg);
		if (!entry) {
			const open = expanded.has(gKey);
			return (
				<SidebarRow
					key={key}
					rowKey={key}
					label={group.pkg}
					depth={0}
					level={1}
					posinset={groups.indexOf(group) + 1}
					setsize={groups.length}
					expanded={open}
					onClick={() => onToggle(gKey)}
					onKeyDown={(e) => {
						if ((e.key === "ArrowRight" && !open) || (e.key === "ArrowLeft" && open)) {
							e.preventDefault();
							onToggle(gKey);
						}
					}}
					icon={
						<>
							<Package aria-hidden="true" className={sidebarIcon(true)} />
							<ChevronRight aria-hidden="true" className={sidebarLaneChevron(open)} />
						</>
					}
				/>
			);
		}
		const row = (
			<SidebarRow
				key={key}
				rowKey={key}
				label={entry.label}
				depth={1}
				level={2}
				posinset={group.entries.indexOf(entry) + 1}
				setsize={group.entries.length}
				onClick={() => make(entry)}
				onKeyDown={(e) => {
					if (e.key === "ArrowLeft") {
						e.preventDefault();
						focusKey(gKey);
					}
				}}
				icon={<PlaneIcon icon={planeIcon(entry.icon)} className={sidebarIcon(false)} />}
			/>
		);
		// Off the sidebar's right edge, anchored on the whole row.
		return entry.description ? (
			<Tooltip key={key}>
				<TooltipTrigger asChild>{row}</TooltipTrigger>
				<TooltipContent side="right" className={sidebarTooltipWide}>
					{entry.description}
				</TooltipContent>
			</Tooltip>
		) : (
			row
		);
	});
}
