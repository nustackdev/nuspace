// A deliberately small markdown renderer for the prose island's read view.
//
// Borrowed engines are the thing this task is trying to avoid, and a markdown
// library is a document model in disguise. This renders to React nodes (never
// raw HTML, so there is no injection surface) and covers exactly what the
// slash menu can produce: headings, lists, quotes, rules, and inline
// bold/italic/code/link.
//
// It is intentionally replaceable. If the prose leaf ever graduates to a real
// inline editor, this file is what gets deleted.

import type { ReactNode } from "react";

const INLINE =
	/(`[^`]+`)|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*]+\*)|(_[^_]+_)|(\[[^\]]+\]\([^)]+\))/;

function inline(text: string, keyBase: string): ReactNode[] {
	const out: ReactNode[] = [];
	let rest = text;
	let i = 0;
	while (rest.length > 0) {
		const m = INLINE.exec(rest);
		if (!m || m.index === undefined) {
			out.push(rest);
			break;
		}
		if (m.index > 0) out.push(rest.slice(0, m.index));
		const tok = m[0];
		const key = `${keyBase}-${i++}`;
		if (tok.startsWith("`")) {
			out.push(
				<code
					key={key}
					className="rounded-sm bg-bg-sunken px-1 py-0.5 font-mono text-[0.9em] text-text-primary"
				>
					{tok.slice(1, -1)}
				</code>,
			);
		} else if (tok.startsWith("**") || tok.startsWith("__")) {
			out.push(
				<strong key={key} className="font-semibold">
					{tok.slice(2, -2)}
				</strong>,
			);
		} else if (tok.startsWith("[")) {
			const cut = tok.indexOf("](");
			out.push(
				<a
					key={key}
					href={tok.slice(cut + 2, -1)}
					className="text-accent underline underline-offset-2"
					target="_blank"
					rel="noreferrer"
				>
					{tok.slice(1, cut)}
				</a>,
			);
		} else {
			out.push(
				<em key={key} className="italic">
					{tok.slice(1, -1)}
				</em>,
			);
		}
		rest = rest.slice(m.index + tok.length);
	}
	return out;
}

const HEADING_CLASS: Record<number, string> = {
	1: "text-3xl font-semibold tracking-tight mt-6 mb-2 first:mt-0",
	2: "text-2xl font-semibold tracking-tight mt-5 mb-2 first:mt-0",
	3: "text-xl font-semibold tracking-tight mt-4 mb-1.5 first:mt-0",
};

/** Render markdown source as React nodes. Block-level, line-oriented. */
export function renderMarkdown(source: string): ReactNode {
	const lines = source.split("\n");
	const out: ReactNode[] = [];
	let i = 0;
	let key = 0;

	const push = (node: ReactNode) => {
		out.push(node);
	};

	while (i < lines.length) {
		const line = lines[i];

		if (line.trim() === "") {
			i += 1;
			continue;
		}

		if (/^(---|\*\*\*|___)\s*$/.test(line)) {
			push(<hr key={key++} className="my-5 border-border-subtle" />);
			i += 1;
			continue;
		}

		const h = /^(#{1,3})\s+(.*)$/.exec(line);
		if (h) {
			const level = h[1].length;
			const Tag = (level === 1 ? "h1" : level === 2 ? "h2" : "h3") as "h1";
			push(
				<Tag key={key++} className={HEADING_CLASS[level]}>
					{inline(h[2], `h${key}`)}
				</Tag>,
			);
			i += 1;
			continue;
		}

		if (/^>\s?/.test(line)) {
			const buf: string[] = [];
			while (i < lines.length && /^>\s?/.test(lines[i])) {
				buf.push(lines[i].replace(/^>\s?/, ""));
				i += 1;
			}
			push(
				<blockquote
					key={key++}
					className="my-2 border-l-2 border-border-strong pl-3 text-text-secondary"
				>
					{inline(buf.join(" "), `q${key}`)}
				</blockquote>,
			);
			continue;
		}

		const bullet = /^\s*[-*+]\s+/;
		const numbered = /^\s*\d+[.)]\s+/;
		if (bullet.test(line) || numbered.test(line)) {
			const ordered = numbered.test(line);
			const re = ordered ? numbered : bullet;
			const items: string[] = [];
			while (i < lines.length && re.test(lines[i])) {
				items.push(lines[i].replace(re, ""));
				i += 1;
			}
			const Tag = ordered ? "ol" : "ul";
			push(
				<Tag
					key={key++}
					className={`my-2 space-y-1 pl-5 ${ordered ? "list-decimal" : "list-disc"} marker:text-text-muted`}
				>
					{items.map((it, n) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: list items are positional
						<li key={n}>{inline(it, `li${key}-${n}`)}</li>
					))}
				</Tag>,
			);
			continue;
		}

		// Paragraph: consume until a blank line or the start of another block.
		const buf: string[] = [];
		while (
			i < lines.length &&
			lines[i].trim() !== "" &&
			!/^(#{1,3}\s|>\s?|---|\*\*\*|___)/.test(lines[i]) &&
			!bullet.test(lines[i]) &&
			!numbered.test(lines[i])
		) {
			buf.push(lines[i]);
			i += 1;
		}
		push(
			<p key={key++} className="my-2 leading-relaxed first:mt-0 last:mb-0">
				{inline(buf.join(" "), `p${key}`)}
			</p>,
		);
	}

	return out;
}
