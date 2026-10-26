// Our icon pack: the lucide names the picker offers, by name, in loose groups.
//
// What is offered, not what draws: the kit draws any lucide name
// (`iconFor`), so a plane or a registered Plane can name an icon the pack
// leaves out and it still shows. The pack is the picker's short list, sorted
// into groups a person can scan.
//
// Names are lucide's own kebab names. `keywords` is extra words the picker's
// search matches on, beyond the name and the group.

/** The pack's groups, in the order the picker shows them. */
export const PACK_GROUPS = [
	{ id: "files", label: "Files" },
	{ id: "work", label: "Work" },
	{ id: "data", label: "Data" },
	{ id: "dev", label: "Dev" },
	{ id: "media", label: "Media" },
	{ id: "people", label: "People" },
	{ id: "places", label: "Places" },
	{ id: "symbols", label: "Symbols" },
] as const;

export type PackGroup = (typeof PACK_GROUPS)[number]["id"];

export type PackIcon = {
	/** lucide's kebab name, what `lucide:<name>` stores. */
	name: string;
	group: PackGroup;
	/** Extra search words, space separated. */
	keywords: string;
};

/** What a plane with no icon of its own shows. */
export const DEFAULT_ICON_NAME = "file-text";

type Entry = readonly [name: string, keywords?: string];

const PACK: Record<PackGroup, readonly Entry[]> = {
	files: [
		["file-text", "document page note"],
		["type", "text font prose writing"],
		["file", "document blank"],
		["folder", "directory"],
		["folder-open", "directory"],
		["notebook-pen", "journal notes write"],
		["book-open", "read docs guide"],
		["book", "read"],
		["library", "books shelf"],
		["archive", "box old"],
		["inbox", "mail tray"],
		["clipboard", "paste"],
		["sticky-note", "memo"],
		["bookmark", "save"],
		["paperclip", "attach"],
		["newspaper", "news article"],
	],
	work: [
		["briefcase", "job work"],
		["list", "items"],
		["list-todo", "tasks todo"],
		["list-checks", "tasks done"],
		["square-check-big", "done task checkbox"],
		["calendar", "date schedule"],
		["clock", "time"],
		["timer", "time stopwatch"],
		["target", "goal aim"],
		["flag", "milestone"],
		["kanban", "board"],
		["rocket", "launch ship"],
		["lightbulb", "idea"],
		["trophy", "win award"],
	],
	data: [
		["activity", "pulse runs"],
		["chart-line", "graph"],
		["chart-column", "graph bar"],
		["chart-pie", "graph"],
		["trending-up", "growth"],
		["gauge", "meter speed"],
		["database", "storage store"],
		["table", "grid spreadsheet"],
		["layers", "stack"],
		["sigma", "sum math"],
		["calculator", "math"],
		["hash", "number"],
	],
	dev: [
		["cpu", "chip processor worker"],
		["code", "program"],
		["square-terminal", "shell console cli"],
		["braces", "json code"],
		["bug", "debug issue"],
		["scan-search", "lens inspect browse"],
		["git-branch", "version"],
		["server", "host"],
		["cloud", "remote"],
		["network", "graph nodes"],
		["workflow", "flow pipeline"],
		["box", "cell container"],
		["boxes", "containers"],
		["package", "box module"],
		["puzzle", "plugin extension"],
		["wrench", "tool fix"],
		["cog", "settings gear"],
		["zap", "fast power bolt"],
		["key", "secret"],
		["lock", "secure private"],
		["shield", "security"],
	],
	media: [
		["image", "picture photo"],
		["camera", "photo"],
		["film", "movie video"],
		["music", "audio song"],
		["headphones", "audio listen"],
		["mic", "audio voice record"],
		["palette", "art colour design"],
		["pen-tool", "design draw"],
		["tv", "screen watch"],
		["gamepad-2", "game play"],
	],
	people: [
		["user", "person me profile"],
		["users", "team group people"],
		["contact", "person card"],
		["mail", "email letter"],
		["message-square", "chat comment"],
		["messages-square", "chat conversation"],
		["phone", "call"],
		["smile", "happy face"],
		["heart", "love like"],
		["handshake", "deal partner"],
	],
	places: [
		["house", "home"],
		["building-2", "office company"],
		["store", "shop"],
		["globe", "world web"],
		["map", "travel"],
		["map-pin", "location place"],
		["compass", "explore direction"],
		["plane", "travel flight"],
		["mountain", "nature"],
		["trees", "nature forest"],
		["sun", "day weather"],
		["moon", "night"],
	],
	symbols: [
		["star", "favourite"],
		["sparkles", "magic new"],
		["flame", "fire hot"],
		["leaf", "nature plant"],
		["sprout", "grow plant"],
		["coffee", "drink break"],
		["gift", "present"],
		["bell", "notify alert"],
		["hexagon", "shape"],
		["diamond", "shape"],
		["atom", "science"],
		["anchor", "harbour"],
		["feather", "light write"],
		["crown", "king"],
		["gem", "jewel"],
		["tag", "label"],
		["link", "url chain"],
		["search", "find"],
		["wallet", "money"],
		["coins", "money"],
	],
};

/** Every icon in the pack, grouped in `PACK_GROUPS` order. */
export const PACK_ICONS: readonly PackIcon[] = PACK_GROUPS.flatMap(({ id }) =>
	PACK[id].map(([name, keywords = ""]) => ({ name, group: id, keywords })),
);
