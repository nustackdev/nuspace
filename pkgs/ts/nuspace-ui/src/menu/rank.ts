// What a registry menu lists for a query, and in what order: the `/` menu's
// snippets (../plane/SlashMenu.tsx) and the Add plane popup's Planes
// (../sidebar/AddPlane.tsx) alike.
//
// Pure: a menu draws what this returns and steps its keys through the same
// flat list, so a heading is never a stop for the arrows.
//
// With nothing typed, the rows are the registry: grouped, the groups in the
// order their first entry registered, the ungrouped last. With a query,
// only the matches stay, best first: a group ranks by its best row, and rows
// rank by where the query hit, the label's start beating a word's start
// beating anywhere in it, then the name, then a word's start in the group or
// the description.

/** What a registry menu ranks: a registered snippet or Plane, as shipped. */
export type MenuEntry = { name: string; label: string; group?: string; description?: string };

/** The heading over the ungrouped rows, when any other row has a group. */
export const OTHER = "Other";

/** Where the query hit, lower is better. Null: it missed. */
export function menuScore(query: string, item: MenuEntry): number | null {
	const q = query.trim().toLowerCase();
	if (!q) return 0;
	const label = item.label.toLowerCase();
	if (label.startsWith(q)) return 0;
	if (label.split(/\s+/).some((w) => w.startsWith(q))) return 1;
	if (label.includes(q)) return 2;
	if (item.name.toLowerCase().includes(q)) return 3;
	if (startsWord(item.group ?? "", q)) return 4;
	if (startsWord(item.description ?? "", q)) return 5;
	return null;
}

/** Whether a word of `text` starts with `q`: inside a word, prose is noise. */
function startsWord(text: string, q: string): boolean {
	return text
		.toLowerCase()
		.split(/[^a-z0-9]+/)
		.some((w) => w.startsWith(q));
}

/** One heading and its rows. `heading` is null when nothing is grouped. */
export type MenuSection<T extends MenuEntry = MenuEntry> = { heading: string | null; items: T[] };

/** The menu's sections for `query`, in order. Empty when nothing matches. */
export function menuSections<T extends MenuEntry>(query: string, items: T[]): MenuSection<T>[] {
	const grouped = items.some((i) => i.group);
	const sections = new Map<
		string,
		{ at: number; best: number; rows: { item: T; score: number; at: number }[] }
	>();
	items.forEach((item, at) => {
		const score = menuScore(query, item);
		if (score === null) return;
		const key = item.group ?? "";
		let s = sections.get(key);
		if (!s) {
			// Ungrouped sorts after every group while nothing is typed.
			s = { at: key ? at : Number.MAX_SAFE_INTEGER, best: score, rows: [] };
			sections.set(key, s);
		}
		s.best = Math.min(s.best, score);
		s.rows.push({ item, score, at });
	});
	return [...sections.entries()]
		.sort(([, a], [, b]) => a.best - b.best || a.at - b.at)
		.map(([key, s]) => ({
			heading: grouped ? key || OTHER : null,
			items: s.rows.sort((a, b) => a.score - b.score || a.at - b.at).map((r) => r.item),
		}));
}

/** The rows in menu order, flat: what the arrows step through. */
export function menuItems<T extends MenuEntry>(query: string, items: T[]): T[] {
	return menuSections(query, items).flatMap((s) => s.items);
}

/** Where `query` sits in `label`, to light it: a word's start first, else the first hit. */
export function menuMatch(query: string, label: string): [number, number] | null {
	const q = query.trim().toLowerCase();
	if (!q) return null;
	const l = label.toLowerCase();
	const word = l.search(new RegExp(`(^|\\s)${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
	const at = word === -1 ? l.indexOf(q) : word === 0 && l.startsWith(q) ? 0 : word + 1;
	return at === -1 ? null : [at, at + q.length];
}
