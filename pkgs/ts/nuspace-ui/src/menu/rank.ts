// What a registry menu lists for a query, and in what order: the `/` menu's
// Cells (../plane/SlashMenu.tsx) and the Add plane popup's Planes
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
//
// Over the groups, one fold more: the package an entry ships in, the name
// before its dot (`nudemos.memes` is nudemos'). Nuverse's rows sit unfolded on
// top, with the menu's pinned rows; every other package is a title with how
// many rows it holds, open only while the lit row is in it. The arrows step
// the rows alone, every package's, folded or not, so stepping into a package
// is what opens it; a title is never a stop. Typing opens them all.

/** What a registry menu ranks: a registered Cell or Plane, as shipped, named `pkg.name`. */
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
	// The name past its package: `nuverse.slider` is found by "slid", not by "nu".
	if (
		item.name
			.slice(item.name.lastIndexOf(".") + 1)
			.toLowerCase()
			.includes(q)
	)
		return 3;
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

/** The package an entry ships in: its name before the first dot, "" for none. */
export function packageOf(name: string): string {
	const dot = name.indexOf(".");
	return dot === -1 ? "" : name.slice(0, dot);
}

/** The package that never folds: its rows sit on top, under the menu's pinned rows. */
export const FIRST_PACKAGE = "nuverse";

/** One package's fold and the sections inside it. */
export type MenuPackage<T extends MenuEntry = MenuEntry> = {
	/** The package, "" for the entries with none. Null on rows with no title: pinned, nuverse's, or a list from one package. */
	key: string | null;
	/** What its title reads. */
	label: string;
	/** How many rows it holds for the query. */
	count: number;
	/** Whether its rows show. A folded package's rows are still the arrows' stops. */
	open: boolean;
	sections: MenuSection<T>[];
};

/** Rows with no title, always open. For a menu's pinned rows. */
export function menuPinned<T extends MenuEntry>(sections: MenuSection<T>[]): MenuPackage<T> {
	const count = sections.reduce((n, s) => n + s.items.length, 0);
	return { key: null, label: "", count, open: true, sections };
}

/**
 * The menu's packages for `query`, in order: nuverse untitled on top, then
 * the rest, in the registry's order or, with a query, best match first. Only
 * the package holding `lit` (an entry's name) is open, until a query opens all.
 */
export function menuPackages<T extends MenuEntry>(
	query: string,
	items: T[],
	lit?: string,
): MenuPackage<T>[] {
	const byPackage = new Map<string, T[]>();
	for (const item of items) {
		const key = packageOf(item.name);
		const rows = byPackage.get(key);
		if (rows) rows.push(item);
		else byPackage.set(key, [item]);
	}
	if (byPackage.size <= 1) {
		const sections = menuSections(query, items);
		return sections.length === 0 ? [] : [menuPinned(sections)];
	}
	const typed = query.trim() !== "";
	const keys = [...byPackage.keys()];
	const litPackage = lit === undefined ? null : packageOf(lit);
	return keys
		.map((key) => {
			const rows = byPackage.get(key) ?? [];
			const sections = menuSections(query, rows);
			const best = Math.min(...rows.map((r) => menuScore(query, r) ?? Number.MAX_SAFE_INTEGER));
			return { key, sections, best };
		})
		.filter((p) => p.sections.length > 0)
		.sort(
			(a, b) =>
				Number(b.key === FIRST_PACKAGE) - Number(a.key === FIRST_PACKAGE) ||
				(typed ? a.best - b.best : 0) ||
				keys.indexOf(a.key) - keys.indexOf(b.key),
		)
		.map(({ key, sections }) =>
			key === FIRST_PACKAGE
				? menuPinned(sections)
				: {
						key,
						label: key || OTHER,
						count: sections.reduce((n, s) => n + s.items.length, 0),
						open: typed || key === litPackage,
						sections,
					},
		);
}

/** Every row in menu order, folded or not: what the arrows step through. */
export function menuRows<T extends MenuEntry>(packages: MenuPackage<T>[]): T[] {
	return packages.flatMap((p) => p.sections.flatMap((s) => s.items));
}
