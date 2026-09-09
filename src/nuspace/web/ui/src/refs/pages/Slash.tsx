// The slash menu.
//
// Two ways in, one list out:
//
// - inline: `/` typed at the start of a line inside a prose island. Focus
//   stays in the textarea (moving it would collapse the caret and commit), so
//   the menu is presentational and the island forwards arrow/enter/escape.
// - insert: the `+` in a block's gutter. Nothing is typing, so the menu takes
//   focus itself.
//
// Actions split by what they do to document structure. A "prefix" item is
// pure text: it rewrites the current line's markdown and the island stays one
// section. "text" / "program" / "split" are structural: they split the island
// at the caret, which is the only way a new section is ever born out of prose.
// Splitting is always explicit -- that is the rule the island model rests on.

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
import { docSlashMenu, docSlashMenuHint, docSlashMenuItem, docSlashMenuLabel } from "../../design";

// What a fresh program block starts life as. A section is a nu.prog
// program: a python *module* with an `out` entry point returning a Nu
// term, not a bare expression. The entry point's signature is the scope
// contract and nuspace offers one value, `path`, which is this block's
// own namespace. Seeding the skeleton is how that is discoverable
// without reading docs first.
export const PROGRAM_TEMPLATE = [
	"import nu",
	"import nu.ui",
	"",
	"",
	"def out(path):",
	'    return nu.ui.TextRef(path + ".out").set(nu.Str("hello"))',
	"",
].join("\n");

export type SlashAction =
	| { kind: "prefix"; prefix: string }
	| { kind: "literal"; text: string }
	| { kind: "split"; insert: "prose" | "program" | null };

export type SlashItem = {
	id: string;
	label: string;
	hint: string;
	group: string;
	keywords: string;
	/** Row glyph. A menu of eleven identical text rows scans as a wall. */
	icon: LucideIcon;
	action: SlashAction;
};

export const SLASH_ITEMS: SlashItem[] = [
	{
		id: "text",
		label: "Text",
		hint: "text",
		group: "blocks",
		keywords: "text paragraph prose p",
		icon: Type,
		action: { kind: "split", insert: "prose" },
	},
	{
		id: "program",
		label: "Program",
		hint: "nu",
		group: "blocks",
		keywords: "program code nu python live section",
		icon: SquareTerminal,
		action: { kind: "split", insert: "program" },
	},
	{
		id: "split",
		label: "Split here",
		hint: "split",
		group: "blocks",
		keywords: "split break divide separate",
		icon: SeparatorHorizontal,
		action: { kind: "split", insert: null },
	},
	{
		id: "h1",
		label: "Heading 1",
		hint: "#",
		group: "prose",
		keywords: "h1 heading title big",
		icon: Heading1,
		action: { kind: "prefix", prefix: "# " },
	},
	{
		id: "h2",
		label: "Heading 2",
		hint: "##",
		group: "prose",
		keywords: "h2 heading subtitle",
		icon: Heading2,
		action: { kind: "prefix", prefix: "## " },
	},
	{
		id: "h3",
		label: "Heading 3",
		hint: "###",
		group: "prose",
		keywords: "h3 heading small",
		icon: Heading3,
		action: { kind: "prefix", prefix: "### " },
	},
	{
		id: "bullet",
		label: "Bulleted list",
		hint: "-",
		group: "prose",
		keywords: "bullet list ul unordered item",
		icon: List,
		action: { kind: "prefix", prefix: "- " },
	},
	{
		id: "numbered",
		label: "Numbered list",
		hint: "1.",
		group: "prose",
		keywords: "number ordered list ol",
		icon: ListOrdered,
		action: { kind: "prefix", prefix: "1. " },
	},
	{
		id: "quote",
		label: "Quote",
		hint: ">",
		group: "prose",
		keywords: "quote blockquote cite",
		icon: TextQuote,
		action: { kind: "prefix", prefix: "> " },
	},
	{
		id: "divider",
		label: "Divider",
		hint: "---",
		group: "prose",
		keywords: "divider rule hr line separator",
		icon: Minus,
		action: { kind: "literal", text: "---\n" },
	},
	{
		id: "body",
		label: "Plain text",
		hint: "plain",
		group: "prose",
		keywords: "plain body normal clear strip",
		icon: Pilcrow,
		action: { kind: "prefix", prefix: "" },
	},
];

export function filterSlash(query: string): SlashItem[] {
	const q = query.trim().toLowerCase();
	if (!q) return SLASH_ITEMS;
	return SLASH_ITEMS.filter(
		(i) => i.label.toLowerCase().includes(q) || i.keywords.includes(q) || i.id.startsWith(q),
	);
}

export function SlashMenu({
	items,
	index,
	anchor,
	takeFocus,
	onPick,
	onMove,
	onClose,
}: {
	items: SlashItem[];
	index: number;
	anchor: { x: number; y: number };
	takeFocus: boolean;
	onPick: (item: SlashItem) => void;
	onMove: (delta: number) => void;
	onClose: () => void;
}) {
	const ref = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		if (takeFocus) ref.current?.focus();
	}, [takeFocus]);

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
		// biome-ignore lint/a11y/noStaticElementInteractions: the menu owns the keyboard in insert mode
		<div
			ref={ref}
			tabIndex={takeFocus ? 0 : -1}
			onKeyDown={(e) => {
				if (!takeFocus) return;
				if (e.key === "ArrowDown") {
					e.preventDefault();
					onMove(1);
				} else if (e.key === "ArrowUp") {
					e.preventDefault();
					onMove(-1);
				} else if (e.key === "Enter") {
					e.preventDefault();
					onPick(items[Math.max(0, Math.min(index, items.length - 1))]);
				} else if (e.key === "Escape") {
					e.preventDefault();
					onClose();
				}
			}}
			onBlur={() => {
				if (takeFocus) onClose();
			}}
			className={`${docSlashMenu} fixed outline-none`}
			style={{ top, left }}
		>
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
							<span className="flex-1 truncate text-left">{item.label}</span>
							<span className={`${docSlashMenuHint} font-mono`}>{item.hint}</span>
						</button>
					</div>
				);
			})}
		</div>
	);
}
