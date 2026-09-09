// Markdown in, markdown out.
//
// Storage does not change. `Section.snippet` holds markdown for a prose
// block, the same string it held when the leaf was a textarea, and the
// executor, the store and the wire never learn that a document engine exists
// in the browser. That is the point: the editor is a *view* over markdown,
// not a new format with a markdown export.
//
// Which is why this is hand-written rather than borrowed. A markdown library
// is a document model in disguise, and the one thing that has to be true
// here is that the parser and the serializer are exact inverses of each
// other over the dialect the island can actually produce - which is exactly
// the dialect the slash menu and the input rules offer, and nothing else. A
// general parser accepting far more than we emit is how round-trips start
// churning. `matchDelim` is shared by both directions, so a construct can
// never be emitted unescaped that the parser would then read back
// differently.
//
// The one normalization that is not identity: a paragraph hard-wrapped
// across source lines comes back as a single line. Reflowing is what a
// WYSIWYG *means* - the alternative is showing the author their source
// wrapping as if it were content. Nothing commits unless the document
// actually changed, so untouched blocks never churn on disk.

import type { Mark, Node as PMNode } from "prosemirror-model";
import { markType, nodeType, proseSchema } from "./schema";

/* ============================== source lines ============================= */

/** A source line plus the absolute offset of its first character. */
type Line = { text: string; at: number };

function toLines(src: string): Line[] {
	const out: Line[] = [];
	let at = 0;
	for (const text of src.split("\n")) {
		out.push({ text, at });
		at += text.length + 1;
	}
	return out;
}

/**
 * A run of text with a per-character map back into the source. Paragraphs
 * are built by joining wrapped lines, so the mapping is not affine and has
 * to be carried explicitly. It is what lets a merge put the caret at the
 * seam rather than at one end of the island.
 */
type Src = { text: string; map: number[] };

function joinLines(lines: Line[]): Src {
	const text: string[] = [];
	const map: number[] = [];
	lines.forEach((line, i) => {
		if (i > 0) {
			text.push(" ");
			map.push(line.at);
		}
		for (let k = 0; k < line.text.length; k++) {
			text.push(line.text[k]);
			map.push(line.at + k);
		}
	});
	return { text: text.join(""), map };
}

function sliceSrc(s: Src, from: number, to: number): Src {
	return { text: s.text.slice(from, to), map: s.map.slice(from, to) };
}

/* ============================== inline grammar =========================== */

const ESCAPABLE = /[\\`*_[\]()#+\-.!>]/;

type Delim =
	| { kind: "code"; inner: [number, number]; next: number }
	| { kind: "strong"; inner: [number, number]; next: number }
	| { kind: "em"; inner: [number, number]; next: number }
	| { kind: "link"; inner: [number, number]; next: number; href: string };

/** Index of the next unescaped occurrence of `token` at or after `from`. */
function findUnescaped(text: string, token: string, from: number): number {
	for (let i = from; i <= text.length - token.length; i++) {
		if (text[i] === "\\") {
			i += 1;
			continue;
		}
		if (text.startsWith(token, i)) return i;
	}
	return -1;
}

/**
 * The whole inline grammar, in one place, used by both directions. The
 * serializer escapes exactly what this matches, so nothing it emits can be
 * re-read as markup that was not there.
 */
export function matchDelim(text: string, i: number): Delim | null {
	const c = text[i];

	if (c === "`") {
		const j = findUnescaped(text, "`", i + 1);
		if (j > i + 1) return { kind: "code", inner: [i + 1, j], next: j + 1 };
		return null;
	}

	if (c === "*" || c === "_") {
		const double = c + c;
		if (text.startsWith(double, i)) {
			const j = findUnescaped(text, double, i + 2);
			if (j > i + 2) return { kind: "strong", inner: [i + 2, j], next: j + 2 };
			return null;
		}
		const j = findUnescaped(text, c, i + 1);
		if (j > i + 1) return { kind: "em", inner: [i + 1, j], next: j + 1 };
		return null;
	}

	if (c === "[") {
		const close = findUnescaped(text, "]", i + 1);
		if (close < 0 || text[close + 1] !== "(") return null;
		const end = findUnescaped(text, ")", close + 2);
		if (end < 0) return null;
		return {
			kind: "link",
			inner: [i + 1, close],
			next: end + 1,
			href: text.slice(close + 2, end),
		};
	}

	return null;
}

/* ============================== parse ==================================== */

/** A parsed text node's span in the markdown source, in document order. */
type Anchor = { from: number; to: number };

type Ctx = { anchors: Anchor[] };

function scanInline(s: Src, marks: readonly Mark[], out: PMNode[], ctx: Ctx): void {
	let buf = "";
	let bufFrom = -1;
	let bufTo = -1;

	const flush = () => {
		if (!buf) return;
		out.push(proseSchema.text(buf, marks as Mark[]));
		ctx.anchors.push({ from: bufFrom, to: bufTo });
		buf = "";
		bufFrom = -1;
	};
	const take = (ch: string, at: number) => {
		if (bufFrom < 0) bufFrom = at;
		bufTo = at + 1;
		buf += ch;
	};

	let i = 0;
	while (i < s.text.length) {
		const c = s.text[i];

		if (c === "\\" && i + 1 < s.text.length && ESCAPABLE.test(s.text[i + 1])) {
			take(s.text[i + 1], s.map[i]);
			i += 2;
			continue;
		}

		const d = matchDelim(s.text, i);
		if (d) {
			flush();
			const inner = sliceSrc(s, d.inner[0], d.inner[1]);
			if (d.kind === "code") {
				// Literal span: no escapes, no nested marks. Backticks are what
				// markdown says they are.
				const mark = markType.code.create();
				out.push(proseSchema.text(inner.text, mark.addToSet(marks as Mark[])));
				ctx.anchors.push({
					from: inner.map[0] ?? s.map[i],
					to: (inner.map[inner.map.length - 1] ?? s.map[i]) + 1,
				});
			} else {
				const mark =
					d.kind === "strong"
						? markType.strong.create()
						: d.kind === "em"
							? markType.em.create()
							: markType.link.create({ href: d.href });
				scanInline(inner, mark.addToSet(marks as Mark[]), out, ctx);
			}
			i = d.next;
			continue;
		}

		take(c, s.map[i]);
		i += 1;
	}
	flush();
}

function inlineNodes(lines: Line[], ctx: Ctx): PMNode[] {
	const out: PMNode[] = [];
	scanInline(joinLines(lines), [], out, ctx);
	return out;
}

const RULE = /^(---|\*\*\*|___)\s*$/;
const HEADING = /^(#{1,3})[ \t]+(.*)$/;
const QUOTE = /^>[ \t]?/;
const BULLET = /^([ \t]*)([-*+])([ \t]+)/;
const ORDERED = /^([ \t]*)(\d+)([.)])([ \t]+)/;

function leadingWs(text: string): number {
	const m = /^[ \t]*/.exec(text);
	return m ? m[0].length : 0;
}

function isBlockStart(text: string): boolean {
	return (
		RULE.test(text) ||
		HEADING.test(text) ||
		QUOTE.test(text) ||
		BULLET.test(text) ||
		ORDERED.test(text)
	);
}

function parseList(
	lines: Line[],
	start: number,
	ordered: boolean,
	ctx: Ctx,
): { node: PMNode; next: number } {
	const re = ordered ? ORDERED : BULLET;
	const indent = leadingWs(lines[start].text);
	const items: PMNode[] = [];
	let order = 1;
	let i = start;

	while (i < lines.length) {
		const m = re.exec(lines[i].text);
		if (!m || m[1].length !== indent) break;
		if (ordered && items.length === 0) order = Number(m[2]) || 1;

		const markerLen = m[0].length;
		const body: Line[] = [{ text: lines[i].text.slice(markerLen), at: lines[i].at + markerLen }];
		i += 1;

		// Continuation: anything indented past the marker belongs to this item.
		while (i < lines.length) {
			const t = lines[i].text;
			if (t.trim() === "") {
				const nxt = lines[i + 1];
				if (nxt && nxt.text.trim() !== "" && leadingWs(nxt.text) >= markerLen) {
					body.push({ text: "", at: lines[i].at });
					i += 1;
					continue;
				}
				break;
			}
			if (leadingWs(t) >= markerLen) {
				body.push({ text: t.slice(markerLen), at: lines[i].at + markerLen });
				i += 1;
				continue;
			}
			break;
		}

		let content = parseBlocks(body, ctx);
		if (content.length === 0) content = [nodeType.paragraph.create()];
		// `list_item` is `paragraph block*`, so an item that opens on a nested
		// list still needs a paragraph to hold the caret.
		if (content[0].type !== nodeType.paragraph) {
			content = [nodeType.paragraph.create(), ...content];
		}
		items.push(nodeType.listItem.create(null, content));
	}

	const type = ordered ? nodeType.orderedList : nodeType.bulletList;
	return { node: type.create(ordered ? { order } : null, items), next: i };
}

function parseBlocks(lines: Line[], ctx: Ctx): PMNode[] {
	const out: PMNode[] = [];
	let i = 0;

	while (i < lines.length) {
		const line = lines[i];

		if (line.text.trim() === "") {
			i += 1;
			continue;
		}

		if (RULE.test(line.text)) {
			out.push(nodeType.rule.create());
			i += 1;
			continue;
		}

		const h = HEADING.exec(line.text);
		if (h) {
			const level = h[1].length;
			const at = line.at + h[0].length - h[2].length;
			out.push(nodeType.heading.create({ level }, inlineNodes([{ text: h[2], at }], ctx)));
			i += 1;
			continue;
		}

		if (QUOTE.test(line.text)) {
			const body: Line[] = [];
			while (i < lines.length && QUOTE.test(lines[i].text)) {
				const cut = QUOTE.exec(lines[i].text)?.[0].length ?? 1;
				body.push({
					text: lines[i].text.slice(cut),
					at: lines[i].at + cut,
				});
				i += 1;
			}
			let inner = parseBlocks(body, ctx);
			if (inner.length === 0) inner = [nodeType.paragraph.create()];
			out.push(nodeType.blockquote.create(null, inner));
			continue;
		}

		if (BULLET.test(line.text) || ORDERED.test(line.text)) {
			const ordered = ORDERED.test(line.text);
			const { node, next } = parseList(lines, i, ordered, ctx);
			out.push(node);
			i = next;
			continue;
		}

		const buf: Line[] = [];
		while (i < lines.length && lines[i].text.trim() !== "" && !isBlockStart(lines[i].text)) {
			buf.push(lines[i]);
			i += 1;
		}
		out.push(nodeType.paragraph.create(null, inlineNodes(buf, ctx)));
	}

	return out;
}

/**
 * A source-offset -> document-position map, in document order. Only used to
 * put the caret at the seam after a merge; everything else addresses the
 * document directly.
 */
export type SourceMap = { src: Anchor; pos: number; size: number }[];

export type Parsed = { doc: PMNode; map: SourceMap };

export function parseMarkdown(source: string): Parsed {
	const ctx: Ctx = { anchors: [] };
	let blocks = parseBlocks(toLines(source), ctx);
	if (blocks.length === 0) blocks = [nodeType.paragraph.create()];
	const doc = proseSchema.node("doc", null, blocks);

	// Text nodes come out of the parser in document order, so zipping them
	// against a document walk is enough; no bookkeeping during construction.
	const map: SourceMap = [];
	let n = 0;
	doc.descendants((node, pos) => {
		if (!node.isText) return true;
		const src = ctx.anchors[n++];
		if (src) map.push({ src, pos, size: node.nodeSize });
		return false;
	});
	return { doc, map };
}

/** Document position for a markdown source offset. Clamped, never throws. */
export function posForOffset(parsed: Parsed, offset: number): number {
	const { doc, map } = parsed;
	if (map.length === 0) return 1;
	for (const entry of map) {
		if (offset < entry.src.from) return entry.pos;
		if (offset <= entry.src.to) {
			return entry.pos + Math.min(offset - entry.src.from, entry.size);
		}
	}
	const last = map[map.length - 1];
	return Math.min(last.pos + last.size, doc.content.size);
}

/* ============================== serialize ================================ */

/** Escape only what `matchDelim` would otherwise read back as markup. */
function escapeInline(text: string): string {
	let out = "";
	let i = 0;
	while (i < text.length) {
		const c = text[i];
		if (c === "\\") {
			out += "\\\\";
			i += 1;
			continue;
		}
		if (matchDelim(text, i)) {
			out += `\\${c}`;
			i += 1;
			continue;
		}
		out += c;
		i += 1;
	}
	return out;
}

/** Escape a leading marker so a line of prose is not read back as a block. */
function escapeLineStart(text: string): string {
	if (RULE.test(text)) return `\\${text}`;
	return text.replace(/^(#{1,3}[ \t]|[-*+][ \t]|\d+[.)][ \t]|>)/, (m) => `\\${m}`);
}

function sameMarks(a: readonly Mark[], b: readonly Mark[]): boolean {
	return a.length === b.length && a.every((m, i) => m.eq(b[i]));
}

function openDelim(mark: Mark): string {
	if (mark.type === markType.code) return "`";
	if (mark.type === markType.strong) return "**";
	if (mark.type === markType.em) return "*";
	if (mark.type === markType.link) return "[";
	return "";
}

function closeDelim(mark: Mark): string {
	if (mark.type === markType.code) return "`";
	if (mark.type === markType.strong) return "**";
	if (mark.type === markType.em) return "*";
	if (mark.type === markType.link) return `](${String(mark.attrs.href)})`;
	return "";
}

/**
 * Marks are serialized as a stack, not per text node: `**bold *and* more**`
 * has three runs sharing one strong, and closing and reopening it around
 * each would emit `**bold ****and***...`, which re-parses as nonsense. Marks
 * always arrive in schema order, so a common-prefix compare is enough to
 * decide what stays open.
 */
function serializeInline(node: PMNode): string {
	const runs: { marks: readonly Mark[]; text: string }[] = [];
	node.forEach((child) => {
		if (!child.isText || child.text === undefined) return;
		const last = runs[runs.length - 1];
		if (last && sameMarks(last.marks, child.marks)) last.text += child.text;
		else runs.push({ marks: child.marks, text: child.text });
	});

	let out = "";
	let open: Mark[] = [];

	const closeDown = (keep: number) => {
		for (let i = open.length - 1; i >= keep; i--) out += closeDelim(open[i]);
		open = open.slice(0, keep);
	};

	for (const run of runs) {
		let keep = 0;
		while (keep < open.length && keep < run.marks.length && open[keep].eq(run.marks[keep])) {
			keep += 1;
		}
		closeDown(keep);
		for (let i = keep; i < run.marks.length; i++) {
			out += openDelim(run.marks[i]);
			open.push(run.marks[i]);
		}
		const isCode = run.marks.some((m) => m.type === markType.code);
		out += isCode ? run.text : escapeInline(run.text);
	}
	closeDown(0);

	return escapeLineStart(out);
}

function prefixLines(text: string, first: string, rest: string): string {
	return text
		.split("\n")
		.map((l, i) => (i === 0 ? first + l : l === "" ? rest.trimEnd() : rest + l))
		.join("\n");
}

function isList(node: PMNode): boolean {
	return node.type === nodeType.bulletList || node.type === nodeType.orderedList;
}

/**
 * Blocks are separated by a blank line. The exception is inside a list item,
 * where a nested list hangs straight off its parent's line: markdown reads
 * both forms as the same document, but only the tight one is what anyone
 * writes, so it is what we emit.
 */
function serializeChildren(node: PMNode, tight = false): string {
	const parts: { text: string; list: boolean }[] = [];
	node.forEach((child) => {
		const text = serializeBlock(child);
		if (text !== "") parts.push({ text, list: isList(child) });
	});

	let out = "";
	parts.forEach((part, i) => {
		if (i > 0) {
			const glued = tight && (part.list || parts[i - 1].list);
			out += glued ? "\n" : "\n\n";
		}
		out += part.text;
	});
	return out;
}

function serializeBlock(node: PMNode): string {
	switch (node.type) {
		case nodeType.paragraph:
			return serializeInline(node);

		case nodeType.heading:
			return `${"#".repeat(node.attrs.level as number)} ${serializeInline(node)}`;

		case nodeType.rule:
			return "---";

		case nodeType.blockquote:
			return prefixLines(serializeChildren(node), "> ", "> ");

		case nodeType.bulletList: {
			const items: string[] = [];
			node.forEach((item) => {
				items.push(prefixLines(serializeChildren(item, true), "- ", "  "));
			});
			return items.join("\n");
		}

		case nodeType.orderedList: {
			const start = (node.attrs.order as number) ?? 1;
			const items: string[] = [];
			node.forEach((item, _offset, index) => {
				const marker = `${start + index}. `;
				items.push(prefixLines(serializeChildren(item, true), marker, " ".repeat(marker.length)));
			});
			return items.join("\n");
		}

		default:
			return serializeChildren(node);
	}
}

/**
 * The document as markdown. Empty means empty: a lone empty paragraph is the
 * resting state of a fresh block and must serialize to "", not "\n", or
 * every new block would arrive dirty.
 */
export function serializeMarkdown(doc: PMNode): string {
	const body = serializeChildren(doc);
	return body === "" ? "" : `${body}\n`;
}

/**
 * Markdown for a range of the document. Used by the explicit split, where
 * the cut lands mid-paragraph. `cut` rather than `slice`: the two halves are
 * about to become two separate sections, so a half-open node is fine and
 * schema validation would only get in the way.
 */
export function serializeRange(doc: PMNode, from: number, to: number): string {
	return serializeMarkdown(doc.cut(from, to));
}
