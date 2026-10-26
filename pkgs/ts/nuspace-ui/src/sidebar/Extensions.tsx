// The extensions, the body's last section, under the planes: what the installed
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
// A group row looks like a tree row (./PlaneRow.tsx): a package icon at rest
// that turns into the fold chevron on hover. But a package is nothing to
// open, so the whole row is one button: a click anywhere on it, Enter or
// Space folds and unfolds it, and so do the arrows. An entry row makes its
// plane with a click anywhere on it, Enter or Space, and its description
// shows in a tooltip off the rail's right edge.

import { Tooltip, TooltipContent, TooltipTrigger } from "@nustackdev/ui-kit";
import { ChevronRight, Package } from "lucide-react";
import { openHere } from "../core/router";
import {
	railGroupLabel,
	railIcon,
	railLaneChevron,
	railTooltipWide,
	railTreeList,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { planeIcon } from "../icon/parse";
import { createPlane } from "./add";
import type { Notify } from "./ops";
import { RailRow } from "./RailRow";
import { RailSection } from "./RailSection";
import type { Registered } from "./types";
import { useRailNav } from "./useRailFocus";

/** One package's group: its name, and the Planes it registers, in order. */
export type ExtensionGroup = { pkg: string; entries: Registered[] };

/** The fold key of a package's group, apart from every plane id. */
export const groupKey = (pkg: string) => `ext:${pkg}`;

/** The package a registered Plane's name belongs to, "" for none. */
export function packageOf(name: string): string {
	const dot = name.indexOf(".");
	return dot > 0 ? name.slice(0, dot) : "";
}

/** The registered Planes by package, packages in the order they first show. */
export function extensionGroups(registered: Registered[]): ExtensionGroup[] {
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
export type ExtensionLine = { key: string; group: ExtensionGroup; entry?: Registered };

/** The section's visible lines, in order: each group, then its entries while it is open. */
export function extensionLines(groups: ExtensionGroup[], expanded: Set<string>): ExtensionLine[] {
	const out: ExtensionLine[] = [];
	for (const group of groups) {
		const gKey = groupKey(group.pkg);
		out.push({ key: gKey, group });
		if (expanded.has(gKey))
			for (const entry of group.entries) out.push({ key: `${gKey}/${entry.name}`, group, entry });
	}
	return out;
}

export function Extensions({
	groups,
	lines,
	expanded,
	onToggle,
	notify,
}: {
	groups: ExtensionGroup[];
	/** `extensionLines` of `groups`, worked out once in ./Rail.tsx for the body's focus order. */
	lines: ExtensionLine[];
	expanded: Set<string>;
	onToggle: (key: string) => void;
	notify: Notify;
}) {
	const { tabKey, setActiveKey, focusKey, arrows } = useRailNav();

	if (!groups.length) return null;

	const make = (entry: Registered) => openHere(createPlane(notify, entry));

	return (
		<>
			<RailSection label="Extensions" />
			<div role="tree" aria-label="Extensions" className={railTreeList}>
				{lines.map(({ key, group, entry }) => {
					const gKey = groupKey(group.pkg);
					if (!entry) {
						const open = expanded.has(gKey);
						return (
							<RailRow
								key={key}
								rowKey={key}
								selected={false}
								tabbable={key === tabKey}
								indent={0}
								level={1}
								posinset={groups.indexOf(group) + 1}
								setsize={groups.length}
								expanded={open}
								onFocus={() => setActiveKey(key)}
								onKeyDown={(e) => {
									if (arrows(e, key)) return;
									const flips =
										e.key === "Enter" ||
										e.key === " " ||
										(e.key === "ArrowRight" && !open) ||
										(e.key === "ArrowLeft" && open);
									if (!flips) return;
									e.preventDefault();
									onToggle(gKey);
								}}
								onClick={() => onToggle(gKey)}
								lane={
									<>
										<Package aria-hidden="true" className={railIcon(true)} />
										<ChevronRight aria-hidden="true" className={railLaneChevron(open)} />
									</>
								}
								label={<span className={railGroupLabel}>{group.pkg}</span>}
								actions={null}
								menu={null}
							/>
						);
					}
					const row = (
						<RailRow
							key={key}
							rowKey={key}
							selected={false}
							tabbable={key === tabKey}
							indent={1}
							level={2}
							posinset={group.entries.indexOf(entry) + 1}
							setsize={group.entries.length}
							onFocus={() => setActiveKey(key)}
							onKeyDown={(e) => {
								if (arrows(e, key)) return;
								if (e.key === "ArrowLeft") {
									e.preventDefault();
									focusKey(gKey);
								} else if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									make(entry);
								}
							}}
							lane={<PlaneIcon icon={planeIcon(entry.icon)} className={railIcon(false)} />}
							onClick={() => make(entry)}
							label={<span className={railGroupLabel}>{entry.label}</span>}
							actions={null}
							menu={null}
						/>
					);
					// Off the rail's right edge, anchored on the whole row.
					return entry.description ? (
						<Tooltip key={key}>
							<TooltipTrigger asChild>{row}</TooltipTrigger>
							<TooltipContent side="right" className={railTooltipWide}>
								{entry.description}
							</TooltipContent>
						</Tooltip>
					) : (
						row
					);
				})}
			</div>
		</>
	);
}
