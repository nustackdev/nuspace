// The standard emoji set, loaded when the picker first shows its Emoji tab.
//
// The data is `unicode-emoji-json`'s by-group file: every fully qualified
// emoji with its Unicode name and group, bundled, never fetched from anywhere
// else. It is a dynamic import, so vite puts it in a chunk of its own and the
// main bundle does not carry it until someone opens the tab.
//
// Emoji newer than 15.0 are left out: a system font that cannot draw one shows
// a box, and 15.0 is what the platforms people run draw today. Skin tone
// variants are not offered; the default is.

export type Emoji = {
	char: string;
	/** Unicode's name, eg "grinning face". */
	name: string;
};

export type EmojiGroup = { label: string; emojis: Emoji[] };

type Raw = {
	name: string;
	emojis: { emoji: string; name: string; emoji_version: string }[];
}[];

/** The newest emoji version offered. */
const NEWEST = 15.0;

/** "Smileys & Emotion" reads "Smileys & emotion": UI copy is sentence case. */
function sentence(label: string): string {
	const lower = label.toLowerCase();
	return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/** Pure, so it is testable without the data file. */
export function shapeEmoji(raw: Raw): EmojiGroup[] {
	return raw
		.map((group) => ({
			label: sentence(group.name),
			emojis: group.emojis
				.filter((e) => Number.parseFloat(e.emoji_version) <= NEWEST)
				.map((e) => ({ char: e.emoji, name: e.name })),
		}))
		.filter((group) => group.emojis.length > 0);
}

let loading: Promise<EmojiGroup[]> | null = null;

/** The emoji, once. A failed load is forgotten, so the next open tries again. */
export function loadEmoji(): Promise<EmojiGroup[]> {
	loading ??= import("unicode-emoji-json/data-by-group.json").then(
		(mod) => shapeEmoji(mod.default as Raw),
		(err: unknown) => {
			loading = null;
			throw err;
		},
	);
	return loading;
}
