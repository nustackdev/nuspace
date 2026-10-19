// What a registry menu draws: the inside of one row, and the key hints along
// its bottom. The row element itself is the menu's (a cmdk item in the Add
// plane popup, a button in the slash menu); it wears `menuItem`.

import { Shortcut } from "@nustackdev/ui-kit";
import { type RefObject, useLayoutEffect, useRef, useState } from "react";
import {
	menuDescription,
	menuEnter,
	menuFloat,
	menuFloatDescription,
	menuFloatLabel,
	menuFloatRow,
	menuFooter,
	menuHit,
	menuKey,
	menuLabel,
	menuText,
	menuTile,
} from "../design";
import { PlaneIcon } from "../icon/PlaneIcon";
import { type Icon, parseIcon } from "../icon/parse";
import { menuMatch } from "./rank";

/**
 * One row's inside: its icon in a tile, the label lit where `query` hit, the
 * description under it. A row that cuts its text off also carries the whole of
 * it, floated over the list while the row is lit (`menuFloat`).
 */
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
	const text = useRef<HTMLSpanElement | null>(null);
	const clipped = useClipped(text, `${label}\n${description ?? ""}\n${query}`);
	const glyph = parseIcon(icon) ?? fallback;
	return (
		<>
			<span className={menuTile}>
				<PlaneIcon icon={glyph} />
			</span>
			<span ref={text} className={menuText}>
				<Label label={label} query={query} className={menuLabel} />
				{description ? <span className={menuDescription}>{description}</span> : null}
			</span>
			<Shortcut keys={["enter"]} className={menuEnter} />
			{clipped ? (
				<span aria-hidden="true" className={menuFloat}>
					<span className={menuFloatRow}>
						<span className={menuTile}>
							<PlaneIcon icon={glyph} />
						</span>
						<span className={menuText}>
							<Label label={label} query={query} className={menuFloatLabel} />
							{description ? <span className={menuFloatDescription}>{description}</span> : null}
						</span>
						<Shortcut keys={["enter"]} className={menuEnter} />
					</span>
				</span>
			) : null}
		</>
	);
}

/** Whether a line under `ref` is cut off, kept true to the row's width as it changes. */
function useClipped(ref: RefObject<HTMLElement | null>, text: string): boolean {
	const [clipped, setClipped] = useState(false);
	// biome-ignore lint/correctness/useExhaustiveDependencies: a new text is a new measure
	useLayoutEffect(() => {
		const el = ref.current;
		if (!el) return;
		const measure = () =>
			setClipped(Array.from(el.children).some((line) => line.scrollWidth > line.clientWidth));
		measure();
		const watch = new ResizeObserver(measure);
		watch.observe(el);
		return () => watch.disconnect();
	}, [ref, text]);
	return clipped;
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
