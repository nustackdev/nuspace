// The slash menu.
//
// Two ways in, and what they offer is NOT the same list:
//
// - inline: `/` typed at the start of a line inside a text block. Prose items
//   only. Somebody mid-paragraph is choosing how this line looks, not what
//   kind of block to make next, so offering "Program" there would answer a
//   question nobody asked. Focus stays in the editor (moving it would
//   collapse the caret and commit), so the menu is presentational and the
//   block forwards arrow/enter/escape.
// - ghost: a ghost input -- the not-yet-a-block line at the end of the page,
//   or the one a gutter `+` summons. Everything, because a ghost is precisely
//   where you choose what to make. Focus stays in the ghost's own input for
//   the same reason it stays in the editor, and the ghost forwards the keys.
//
// Neither way takes focus, which is why this component has no keyboard of its
// own: it draws a list and reports clicks. That used to be untrue -- the `+`
// opened it with nothing typing and it grabbed focus itself -- and the `+`
// does not open it any more.
//
// Actions split by what they do to document structure. A "prefix" item is
// pure text: it rewrites the current line's markdown and the block stays one
// block. The snippet rows and "split" are structural: they split the block at
// the caret, which is the only way a new block is ever born out of text.
// Splitting is always explicit -- that is the rule the block model rests on.
//
// From a ghost there is no line to rewrite and nothing to split, so the same
// two actions mean the other thing there: a prefix SEEDS a new text block
// with that shape, and a split just makes the block it names. The canvas owns
// that reading -- see `pickSlash`.
//
// `act` is this menu's own discriminant, not block vocabulary. `insert` IS
// block vocabulary: it names a `tpl`, which is what the create op takes.

import {
	Heading1,
	Heading2,
	Heading3,
	List,
	ListOrdered,
	type LucideIcon,
	Minus,
	Pilcrow,
	SeparatorHorizontal,
	SquareTerminal,
	TextQuote,
	Type,
} from "lucide-react";
import { useEffect, useRef } from "react";
import {
	docSlashMenu,
	docSlashMenuHint,
	docSlashMenuItem,
	docSlashMenuItemLabel,
	docSlashMenuLabel,
} from "../../design";
import type { SlashSnippet } from "./state";

export type SlashAction =
	| { act: "prefix"; prefix: string }
	| { act: "literal"; text: string }
	| { act: "split"; insert: string | null };

/** Which surface the menu is open on, and so which items it may offer. */
export type SlashMode = "inline" | "ghost";

/**
 * Structure or shape. "blocks" items make a block, "prose" items shape one.
 * That split is the whole of what scopes the menu, so it is a closed set and
 * not a free-text heading.
 */
export type SlashGroup = "blocks" | "prose";

export type SlashItem = {
	id: string;
	label: string;
	hint: string;
	group: SlashGroup;
	keywords: string;
	/** Row glyph. A menu of eleven identical text rows scans as a wall. */
	icon: LucideIcon;
	action: SlashAction;
};

/** The block rows when no snippets were seeded. */
const FALLBACK_BLOCKS: SlashItem[] = [
	{
		id: "text",
		label: "Text",
		hint: "text",
		group: "blocks",
		keywords: "text paragraph prose p",
		icon: Type,
		action: { act: "split", insert: "text" },
	},
	{
		id: "program",
		label: "Program",
		hint: "nu",
		group: "blocks",
		keywords: "program code nu python live section",
		icon: SquareTerminal,
		action: { act: "split", insert: "program" },
	},
];

/**
 * One block row per registered snippet (D19). The prose one inserts "text",
 * which is prose's wire tpl; every other one inserts its own name, which the
 * create carries as `tpl` and the server resolves to that snippet's prog.
 */
function snippetItems(snippets: SlashSnippet[]): SlashItem[] {
	return snippets.map((s) => ({
		id: `snippet:${s.name}`,
		label: s.label,
		hint: s.text ? "text" : s.name,
		group: "blocks",
		keywords: `${s.name} ${s.label}`.toLowerCase() + (s.text ? " text paragraph prose p" : ""),
		icon: s.text ? Type : SquareTerminal,
		action: { act: "split", insert: s.text ? "text" : s.name },
	}));
}

/** Rows every menu carries whatever is registered. */
const FIXED_ITEMS: SlashItem[] = [
	{
		id: "split",
		label: "Split here",
		hint: "split",
		group: "blocks",
		keywords: "split break divide separate",
		icon: SeparatorHorizontal,
		action: { act: "split", insert: null },
	},
	{
		id: "h1",
		label: "Heading 1",
		hint: "#",
		group: "prose",
		keywords: "h1 heading title big",
		icon: Heading1,
		action: { act: "prefix", prefix: "# " },
	},
	{
		id: "h2",
		label: "Heading 2",
		hint: "##",
		group: "prose",
		keywords: "h2 heading subtitle",
		icon: Heading2,
		action: { act: "prefix", prefix: "## " },
	},
	{
		id: "h3",
		label: "Heading 3",
		hint: "###",
		group: "prose",
		keywords: "h3 heading small",
		icon: Heading3,
		action: { act: "prefix", prefix: "### " },
	},
	{
		id: "bullet",
		label: "Bulleted list",
		hint: "-",
		group: "prose",
		keywords: "bullet list ul unordered item",
		icon: List,
		action: { act: "prefix", prefix: "- " },
	},
	{
		id: "numbered",
		label: "Numbered list",
		hint: "1.",
		group: "prose",
		keywords: "number ordered list ol",
		icon: ListOrdered,
		action: { act: "prefix", prefix: "1. " },
	},
	{
		id: "quote",
		label: "Quote",
		hint: ">",
		group: "prose",
		keywords: "quote blockquote cite",
		icon: TextQuote,
		action: { act: "prefix", prefix: "> " },
	},
	{
		id: "divider",
		label: "Divider",
		hint: "---",
		group: "prose",
		keywords: "divider rule hr line separator",
		icon: Minus,
		action: { act: "literal", text: "---\n" },
	},
	{
		id: "body",
		label: "Plain text",
		hint: "plain",
		group: "prose",
		keywords: "plain body normal clear strip",
		icon: Pilcrow,
		action: { act: "prefix", prefix: "" },
	},
];

/** What the inline trigger may offer. Built once: it never varies. */
const PROSE_ITEMS = FIXED_ITEMS.filter((i) => i.group === "prose");

/** The whole ghost menu: the snippets' block rows, then the fixed rows.
 *  Falls back to plain Text / Program when nothing was seeded. */
export function buildSlashItems(snippets: SlashSnippet[]): SlashItem[] {
	const blocks = snippets.length ? snippetItems(snippets) : FALLBACK_BLOCKS;
	return [...blocks, ...FIXED_ITEMS];
}

/** The menu with nothing registered. */
export const SLASH_ITEMS: SlashItem[] = buildSlashItems([]);

/**
 * The rows this context may show, narrowed by what has been typed.
 *
 * `mode` is not a filter on top of the query, it is the pool the query runs
 * against: an inline `/` cannot reach a "blocks" item however precisely it is
 * spelled, because that item does not mean anything where the caret is.
 */
export function filterSlash(
	query: string,
	mode: SlashMode,
	items: SlashItem[] = SLASH_ITEMS,
): SlashItem[] {
	const pool = mode === "inline" ? PROSE_ITEMS : items;
	const q = query.trim().toLowerCase();
	if (!q) return pool;
	return pool.filter(
		(i) => i.label.toLowerCase().includes(q) || i.keywords.includes(q) || i.id.startsWith(q),
	);
}

export function SlashMenu({
	items,
	index,
	anchor,
	onPick,
	onMove,
}: {
	items: SlashItem[];
	index: number;
	anchor: { x: number; y: number };
	onPick: (item: SlashItem) => void;
	onMove: (delta: number) => void;
}) {
	const ref = useRef<HTMLDivElement | null>(null);

	// Keep the highlighted row visible while filtering narrows the list.
	useEffect(() => {
		ref.current
			?.querySelector<HTMLElement>(`[data-slash-index="${index}"]`)
			?.scrollIntoView({ block: "nearest" });
	}, [index]);

	if (items.length === 0) return null;

	const top = Math.min(anchor.y + 6, window.innerHeight - 300);
	const left = Math.min(anchor.x, window.innerWidth - 280);

	let lastGroup = "";
	return (
		<div ref={ref} className={`${docSlashMenu} fixed outline-none`} style={{ top, left }}>
			{items.map((item, i) => {
				const head = item.group !== lastGroup ? item.group : null;
				lastGroup = item.group;
				return (
					<div key={item.id}>
						{head ? <div className={docSlashMenuLabel}>{head}</div> : null}
						<button
							type="button"
							data-slash-index={i}
							onMouseDown={(e) => {
								// mousedown, not click: click would land after the
								// textarea's blur has already collapsed the caret.
								e.preventDefault();
								onPick(item);
							}}
							onMouseEnter={() => onMove(i - index)}
							data-selected={i === index}
							className={docSlashMenuItem}
						>
							<item.icon aria-hidden="true" />
							<span className={docSlashMenuItemLabel}>{item.label}</span>
							<span className={docSlashMenuHint}>{item.hint}</span>
						</button>
					</div>
				);
			})}
		</div>
	);
}
