// The icon picker: our pack or an emoji, searched, picked from a grid.
//
// Two tabs over one grid. "Icons" is the pack (./pack.ts), in its groups;
// "Emoji" is the standard set, loaded the first time the tab shows (see
// ./emoji.ts). Both lead with this viewer's recent picks of that kind, until
// there is a search.
//
// The search box has the caret when it opens. Typing filters by name, group
// and keywords; Enter there takes the first match and Down steps into the
// grid. In the grid the arrows move by cell and by row, Enter or Space picks,
// and Up off the top row goes back to the search. One cell at a time is in
// the tab order (a roving tabindex), so Tab leaves the grid in one step.
//
// "Remove" clears the plane's icon back to the default. What a pick does is
// the caller's: the picker only says which value was picked.
//
// `IconPickerContent` is the picker in a kit `PopoverContent`; the caller owns
// the `Popover` and its trigger or anchor.

import {
	Button,
	Input,
	PopoverContent,
	Tabs,
	TabsContent,
	TabsList,
	TabsTrigger,
} from "@nustackdev/ui-kit";
import type * as React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	iconPicker,
	iconPickerBody,
	iconPickerCell,
	iconPickerGroup,
	iconPickerHead,
	iconPickerNote,
	iconPickerRemove,
	iconPickerRow,
	iconPickerSearch,
} from "../design";
import { type EmojiGroup, loadEmoji } from "./emoji";
import { PlaneIcon } from "./PlaneIcon";
import { PACK_GROUPS, PACK_ICONS } from "./pack";
import { EMOJI, formatIcon, type Icon, parseIcon } from "./parse";
import { pushRecent, readRecent } from "./recent";

/** Cells per row. Matches `grid-cols-9` in `iconPickerRow`. */
export const COLUMNS = 9;

type Tab = "icons" | "emoji";

type Cell = {
	/** The stored spelling a pick hands back. */
	value: string;
	/** What it is called, for a screen reader and the tooltip. */
	label: string;
	icon: Icon;
	/** Everything the search matches on, lower case. */
	haystack: string;
};

type Section = { label: string; cells: Cell[] };

function iconCells(): Section[] {
	return PACK_GROUPS.map(({ id, label }) => ({
		label,
		cells: PACK_ICONS.filter((i) => i.group === id).map((i) => {
			const words = i.name.replace(/-/g, " ");
			return {
				value: formatIcon({ kind: "lucide", name: i.name }),
				label: words,
				icon: { kind: "lucide", name: i.name } as const,
				haystack: `${words} ${i.name} ${i.keywords} ${label}`.toLowerCase(),
			};
		}),
	}));
}

function emojiCells(groups: EmojiGroup[]): Section[] {
	return groups.map((group) => ({
		label: group.label,
		cells: group.emojis.map((e) => ({
			value: formatIcon({ kind: "emoji", char: e.char }),
			label: e.name,
			icon: { kind: "emoji", char: e.char } as const,
			haystack: `${e.name} ${group.label}`.toLowerCase(),
		})),
	}));
}

/** Every word of the query somewhere in the cell's words. */
function matches(cell: Cell, words: string[]): boolean {
	return words.every((w) => cell.haystack.includes(w));
}

/** The sections a tab shows for a query: recent first when there is none. */
function sectionsFor(all: Section[], recent: string[], query: string): Section[] {
	const words = query.toLowerCase().split(/\s+/).filter(Boolean);
	if (words.length > 0) {
		return all
			.map((s) => ({ label: s.label, cells: s.cells.filter((c) => matches(c, words)) }))
			.filter((s) => s.cells.length > 0);
	}
	const byValue = new Map(all.flatMap((s) => s.cells.map((c) => [c.value, c] as const)));
	const mine = recent.flatMap((v) => byValue.get(v) ?? []);
	return mine.length > 0 ? [{ label: "Recent", cells: mine }, ...all] : all;
}

/** The emoji, once the tab has asked for them. */
function useEmoji(wanted: boolean): EmojiGroup[] | "loading" | "failed" {
	const [state, setState] = useState<EmojiGroup[] | "loading" | "failed">("loading");
	useEffect(() => {
		if (!wanted || state !== "loading") return;
		let live = true;
		loadEmoji().then(
			(groups) => live && setState(groups),
			() => live && setState("failed"),
		);
		return () => {
			live = false;
		};
	}, [wanted, state]);
	return state;
}

export function IconPicker({
	value,
	onPick,
	onRemove,
}: {
	/** The plane's `meta.icon` now. */
	value: string;
	/** A cell was picked: its stored spelling. */
	onPick: (icon: string) => void;
	/** Back to the default. */
	onRemove: () => void;
}) {
	const current = formatIcon(parseIcon(value));
	const [tab, setTab] = useState<Tab>(current.startsWith(EMOJI) ? "emoji" : "icons");
	const [query, setQuery] = useState("");
	const [active, setActive] = useState(0);
	const [recent] = useState(readRecent);
	const emoji = useEmoji(tab === "emoji");
	const rootRef = useRef<HTMLDivElement | null>(null);
	const icons = useMemo(iconCells, []);
	const emojis = useMemo(() => (Array.isArray(emoji) ? emojiCells(emoji) : []), [emoji]);

	const sections = useMemo(
		() =>
			tab === "icons"
				? sectionsFor(
						icons,
						recent.filter((v) => !v.startsWith(EMOJI)),
						query,
					)
				: sectionsFor(
						emojis,
						recent.filter((v) => v.startsWith(EMOJI)),
						query,
					),
		[tab, icons, emojis, recent, query],
	);

	// The grid as rows of flat cell indices, so the arrows can move by row
	// across a group's short last row.
	const { cells, rows, place } = useMemo(() => {
		const cells: Cell[] = [];
		const rows: number[][] = [];
		const place: [row: number, col: number][] = [];
		for (const s of sections) {
			for (let i = 0; i < s.cells.length; i += COLUMNS) {
				const row: number[] = [];
				for (const cell of s.cells.slice(i, i + COLUMNS)) {
					place.push([rows.length, row.length]);
					row.push(cells.length);
					cells.push(cell);
				}
				rows.push(row);
			}
		}
		return { cells, rows, place };
	}, [sections]);

	// A new search or tab starts the grid over, at its top.
	// biome-ignore lint/correctness/useExhaustiveDependencies: the reset is what the query and tab change mean.
	useEffect(() => {
		setActive(0);
		const body = rootRef.current?.querySelector("[data-picker-body]");
		if (body) body.scrollTop = 0;
	}, [query, tab]);

	// The caret starts in the search. Before the popover's own focus pass, so
	// that pass finds focus already inside and leaves it be.
	useEffect(() => {
		rootRef.current?.querySelector<HTMLInputElement>("input")?.focus();
	}, []);

	const pick = useCallback(
		(cell: Cell) => {
			pushRecent(cell.value);
			onPick(cell.value);
		},
		[onPick],
	);

	const focusCell = (i: number) => {
		setActive(i);
		rootRef.current?.querySelector<HTMLElement>(`[data-cell="${i}"]`)?.focus();
	};

	const focusSearch = () => rootRef.current?.querySelector<HTMLInputElement>("input")?.focus();

	const onSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.nativeEvent.isComposing) return;
		if (e.key === "ArrowDown" && cells.length > 0) {
			e.preventDefault();
			focusCell(Math.min(active, cells.length - 1));
		} else if (e.key === "Enter" && cells.length > 0) {
			e.preventDefault();
			pick(cells[0]);
		}
	};

	const onGridKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
		const at = place[active];
		if (!at) return;
		const [r, c] = at;
		const inRow = (row: number[] | undefined) => (row ? row[Math.min(c, row.length - 1)] : -1);
		let next = -1;
		if (e.key === "ArrowRight") next = active + 1 < cells.length ? active + 1 : active;
		else if (e.key === "ArrowLeft") next = active > 0 ? active - 1 : active;
		else if (e.key === "ArrowDown") next = r + 1 < rows.length ? inRow(rows[r + 1]) : active;
		else if (e.key === "ArrowUp") {
			e.preventDefault();
			if (r === 0) focusSearch();
			else focusCell(inRow(rows[r - 1]));
			return;
		} else if (e.key === "Home") next = 0;
		else if (e.key === "End") next = cells.length - 1;
		else return;
		e.preventDefault();
		focusCell(next);
	};

	const body = () => {
		if (tab === "emoji" && emoji === "loading") {
			return <p className={iconPickerNote}>Loading emoji</p>;
		}
		if (tab === "emoji" && emoji === "failed") {
			return <p className={iconPickerNote}>Emoji could not load</p>;
		}
		if (cells.length === 0) return <p className={iconPickerNote}>Nothing matches</p>;
		let base = 0;
		return (
			// biome-ignore lint/a11y/noStaticElementInteractions: the arrows land here from the cells, which are real buttons
			<div onKeyDown={onGridKey}>
				{sections.map((s) => {
					const start = base;
					base += s.cells.length;
					const groupRows: Cell[][] = [];
					for (let i = 0; i < s.cells.length; i += COLUMNS) {
						groupRows.push(s.cells.slice(i, i + COLUMNS));
					}
					return (
						<section key={s.label} aria-label={s.label}>
							<h3 className={iconPickerGroup}>{s.label}</h3>
							{groupRows.map((row, ri) => (
								<div key={row[0].value} className={iconPickerRow}>
									{row.map((cell, ci) => {
										const i = start + ri * COLUMNS + ci;
										return (
											<button
												key={cell.value}
												type="button"
												data-cell={i}
												tabIndex={i === active ? 0 : -1}
												aria-label={cell.label}
												aria-pressed={cell.value === current}
												title={cell.label}
												className={iconPickerCell(cell.value === current)}
												onFocus={() => setActive(i)}
												onClick={() => pick(cell)}
											>
												<PlaneIcon icon={cell.icon} size="md" />
											</button>
										);
									})}
								</div>
							))}
						</section>
					);
				})}
			</div>
		);
	};

	return (
		<div ref={rootRef}>
			<Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-0">
				<div className={iconPickerHead}>
					<TabsList variant="line" className="border-b-0">
						<TabsTrigger value="icons" size="sm">
							Icons
						</TabsTrigger>
						<TabsTrigger value="emoji" size="sm">
							Emoji
						</TabsTrigger>
					</TabsList>
					{value.trim() ? (
						<Button variant="ghost" size="sm" className={iconPickerRemove} onClick={onRemove}>
							Remove
						</Button>
					) : null}
				</div>
				<div className={iconPickerSearch}>
					<Input
						size="sm"
						type="search"
						aria-label={tab === "icons" ? "Search icons" : "Search emoji"}
						placeholder={tab === "icons" ? "Search icons" : "Search emoji"}
						value={query}
						onChange={(e) => setQuery(e.currentTarget.value)}
						onKeyDown={onSearchKey}
					/>
				</div>
				<TabsContent value="icons" tabIndex={-1} className={iconPickerBody} data-picker-body="">
					{tab === "icons" ? body() : null}
				</TabsContent>
				<TabsContent value="emoji" tabIndex={-1} className={iconPickerBody} data-picker-body="">
					{tab === "emoji" ? body() : null}
				</TabsContent>
			</Tabs>
		</div>
	);
}

/**
 * The picker in a kit popover. Put it inside a `Popover` whose trigger or
 * anchor is the icon being changed.
 */
export function IconPickerContent({
	value,
	onPick,
	onRemove,
	...content
}: React.ComponentProps<typeof IconPicker> &
	Omit<React.ComponentProps<typeof PopoverContent>, "children" | "className">) {
	return (
		<PopoverContent className={iconPicker} {...content}>
			<IconPicker value={value} onPick={onPick} onRemove={onRemove} />
		</PopoverContent>
	);
}
