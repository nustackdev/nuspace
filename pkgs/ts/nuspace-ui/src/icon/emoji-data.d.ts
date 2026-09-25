// The one file of `unicode-emoji-json` the picker reads. The package ships no
// types for it, and the app does not turn on `resolveJsonModule` for one file.
declare module "unicode-emoji-json/data-by-group.json" {
	const groups: {
		name: string;
		slug: string;
		emojis: {
			emoji: string;
			name: string;
			slug: string;
			skin_tone_support: boolean;
			unicode_version: string;
			emoji_version: string;
		}[];
	}[];
	export default groups;
}
