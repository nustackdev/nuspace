// What a registry menu draws: the inside of one row, and the key hints along
// its bottom. The row element itself is the menu's (a cmdk item in the Add
// plane popup, a button in the slash menu); it wears `menuItem`.

import { Shortcut } from "@nustackdev/ui-kit";
import { ChevronRight } from "lucide-react";
import {
	menuDescription,
	menuEnter,
	menuFooter,
	menuHit,
	menuKey,
	menuLabel,
	menuPackageChevron,
	menuPackageCount,
	menuText,
	menuTile,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { type Icon, parseIcon } from "../icon/parse";
import { menuMatch } from "./rank";

/** One row's inside: its icon in a tile, the label lit where `query` hit, the description under it, wrapped whole. */
export function MenuEntry({
	icon,
	fallback,
	label,
	description,
	query,
}: {
	/** As the registry spells it (../icon/parse.ts). */
	icon?: string;
	/** What shows when `icon` names nothing drawable. */
	fallback: Icon;
	label: string;
	description?: string;
	query: string;
}) {
	return (
		<>
			<span className={menuTile}>
				<PlaneIcon icon={parseIcon(icon) ?? fallback} />
			</span>
			<span className={menuText}>
				<Label label={label} query={query} className={menuLabel} />
				{description ? <span className={menuDescription}>{description}</span> : null}
			</span>
			<Shortcut keys={["enter"]} className={menuEnter} />
		</>
	);
}

/** A package's title inside: the chevron saying open or folded, its name, its count. */
export function PackageEntry({
	label,
	count,
	open,
}: {
	label: string;
	count: number;
	open: boolean;
}) {
	return (
		<>
			<ChevronRight className={menuPackageChevron(open)} />
			<span className="truncate">{label}</span>
			<span className={menuPackageCount}>{count}</span>
		</>
	);
}

/** The label, the part the query matched lit. */
function Label({ label, query, className }: { label: string; query: string; className: string }) {
	const hit = menuMatch(query, label);
	if (!hit) return <span className={className}>{label}</span>;
	const [from, to] = hit;
	return (
		<span className={className}>
			{label.slice(0, from)}
			<mark className={menuHit}>{label.slice(from, to)}</mark>
			{label.slice(to)}
		</span>
	);
}

/** The keys along the bottom: move, `action` on Enter, close. */
export function MenuKeys({ action }: { action: string }) {
	return (
		<div className={menuFooter}>
			<span className={menuKey}>
				<Shortcut keys={["up"]} size="sm" />
				<Shortcut keys={["down"]} size="sm" />
				Navigate
			</span>
			<span className={menuKey}>
				<Shortcut keys={["enter"]} size="sm" />
				{action}
			</span>
			<span className={menuKey}>
				<Shortcut keys={["esc"]} size="sm" />
				Close
			</span>
		</div>
	);
}
