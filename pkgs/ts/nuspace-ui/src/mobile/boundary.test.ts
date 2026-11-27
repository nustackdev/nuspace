// The mobile shell's boundary: nothing under src/mobile/ reaches the desktop
// only parts, directly or through other src files. The two shells load as
// separate chunks (../shells.ts), so a stray import pulls the desktop's
// layout, drag and drop and editor machinery onto the phone.
//
// Read statically: every file under src/mobile/ (tests aside), its relative
// and `@/` imports followed through src, resolved as the bundler does
// (.ts, .tsx, index). Type-only imports are erased in the build and are not
// followed. Shared state (core/, refs/register.ts, sidebar/state.ts,
// sidebar/tree.ts, pane/state.ts, ...) is fine.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

/**
 * The desktop only entry points, relative to src. A directory forbids every
 * file in it; a name ending in `*` forbids every file it prefixes.
 */
const FORBIDDEN = [
	// The desktop shell and its root.
	"App.tsx",
	"shell/Shell.tsx",
	"refs/desktop.ts",
	// The desktop sidebar (its state and tree are shared; the component is not).
	"sidebar/Sidebar.tsx",
	// The desk canvas: columns, resize, drop regions.
	"main/",
	// Desk drag and drop.
	"desk/drag*",
	"desk/dnd*",
	// The desktop pane and plane editor machinery.
	"pane/Pane.tsx",
	"pane/PaneHeader.tsx",
	"pane/PaneMenu.tsx",
	"plane/Plane.tsx",
	"plane/selection/",
	"plane/structure/",
];

function forbidden(rel: string): string | null {
	for (const rule of FORBIDDEN) {
		if (rule.endsWith("/") || rule.endsWith("*")) {
			if (rel.startsWith(rule.replace(/\*$/, ""))) return rule;
		} else if (rel === rule) return rule;
	}
	return null;
}

const EXTS = [".ts", ".tsx"];

/** A specifier resolved to a file under src, or null when it is a package or not found. */
function resolve(from: string, spec: string): string | null {
	let base: string;
	if (spec.startsWith("@/")) base = path.join(SRC, spec.slice(2));
	else if (spec.startsWith(".")) base = path.resolve(path.dirname(from), spec);
	else return null;
	const tries = [
		base,
		...EXTS.map((e) => base + e),
		...EXTS.map((e) => path.join(base, `index${e}`)),
	];
	for (const t of tries) if (existsSync(t) && statSync(t).isFile()) return t;
	return null;
}

// `import x from "y"`, `export { x } from "y"`, `import "y"`, `import("y")`.
const IMPORT = /(?:^|\n)\s*(import|export)\s+(type\s+)?([^;]*?)\s*from\s*["']([^"']+)["']/g;
const BARE = /(?:^|\n)\s*import\s*["']([^"']+)["']/g;
const DYNAMIC = /import\(\s*["']([^"']+)["']\s*\)/g;

/** The specifiers a file loads at run time: type-only imports left out. */
function specifiers(source: string): string[] {
	const out: string[] = [];
	for (const m of source.matchAll(IMPORT)) {
		if (m[2]) continue;
		// `import { type A, type B } from` is erased too.
		const names = m[3].match(/^\{([^}]*)\}$/)?.[1].split(",");
		const typeOnly = names?.every((n) => !n.trim() || n.trim().startsWith("type "));
		if (typeOnly) continue;
		out.push(m[4]);
	}
	for (const m of source.matchAll(BARE)) out.push(m[1]);
	for (const m of source.matchAll(DYNAMIC)) out.push(m[1]);
	return out;
}

function mobileFiles(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) return mobileFiles(p);
		return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : [];
	});
}

/** Every forbidden file reached from the mobile files, with the chain that reaches it. */
function violations(): string[] {
	const out: string[] = [];
	const via = new Map<string, string | null>();
	const queue: string[] = [];
	for (const f of mobileFiles(path.join(SRC, "mobile"))) {
		via.set(f, null);
		queue.push(f);
	}
	while (queue.length) {
		const file = queue.shift() as string;
		for (const spec of specifiers(readFileSync(file, "utf8"))) {
			const to = resolve(file, spec);
			if (!to || via.has(to)) continue;
			via.set(to, file);
			const rel = path.relative(SRC, to);
			if (forbidden(rel)) {
				const chain = [rel];
				for (let at = via.get(to); at; at = via.get(at) ?? null)
					chain.unshift(path.relative(SRC, at));
				out.push(chain.join(" -> "));
				continue;
			}
			queue.push(to);
		}
	}
	return out;
}

describe("the mobile boundary", () => {
	it("forbids what it says", () => {
		expect(forbidden("main/Desk.tsx")).toBe("main/");
		expect(forbidden("desk/dnd.ts")).toBe("desk/dnd*");
		expect(forbidden("desk/drag.ts")).toBe("desk/drag*");
		expect(forbidden("desk/model.ts")).toBeNull();
		expect(forbidden("sidebar/Sidebar.tsx")).toBe("sidebar/Sidebar.tsx");
		expect(forbidden("sidebar/state.ts")).toBeNull();
		expect(forbidden("App.tsx")).toBe("App.tsx");
		expect(forbidden("mobile/App.tsx")).toBeNull();
	});

	it("skips type-only imports", () => {
		expect(
			specifiers(
				[
					'import type { A } from "./a";',
					'import { type B, type C } from "./b";',
					'import { type D, e } from "./d";',
					'export { f } from "./f";',
					'const g = import("./g");',
				].join("\n"),
			),
		).toEqual(["./d", "./f", "./g"]);
	});

	it("keeps src/mobile/ clear of the desktop only parts", () => {
		expect(violations()).toEqual([]);
	});
});
