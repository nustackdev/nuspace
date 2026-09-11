import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// ============================== TEMPORARY ==================================
//
// nuspace depends on `@nustackdev/ui-kit@0.1.3` from the registry, and 0.1.3
// predates `ProseRef` and its ProseMirror editor. A text block is a Nu
// program holding a ProseRef, so nuspace cannot render a document without
// them. Rather than publish a kit release from here, the build resolves the
// kit to its SOURCE in the sibling `nu` checkout.
//
// Consequences, both real:
//
//   - a clean checkout of nuspace alone DOES NOT BUILD. The nu repo has to be
//     next to it, at ~/Projects/nustackdev/nu, which is the standard layout.
//   - the same mapping is repeated in tsconfig.app.json, because `tsc -b`
//     runs before vite and does its own resolution.
//
// Delete all of it the moment the kit publishes a version with ProseRef in
// it: drop this block, drop the tsconfig `paths`, bump the dependency.
//
// `dedupe` is not optional. The kit source sits inside nu's own npm
// workspace, which has its own `react`, so without it a page ends up with
// two React copies and every hook in a kit component throws.
const KIT_SRC = path.resolve(__dirname, "../../../../../nu/packages/nustd/src/nu/ui/web/kit/src");
const REACT = path.resolve(__dirname, "node_modules/react");
const REACT_DOM = path.resolve(__dirname, "node_modules/react-dom");

export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: {
		// Regexes, anchored, because a plain string `find` is a PREFIX match:
		// ".../ui-kit/refs" as a string would also swallow ".../ui-kit/refs/
		// input/prose/markdown" and rewrite it to nonsense. Order still
		// matters, so the published subpaths resolve before the catch-all.
		alias: [
			{ find: /^@nustackdev\/ui-kit\/styles$/, replacement: `${KIT_SRC}/index.css` },
			{ find: /^@nustackdev\/ui-kit\/store$/, replacement: `${KIT_SRC}/store.ts` },
			{ find: /^@nustackdev\/ui-kit\/refs$/, replacement: `${KIT_SRC}/refs/index.ts` },
			// The catch-all. Only one import uses it -- see refs/pages/prose.ts,
			// which explains why and what has to happen before the kit ships.
			{ find: /^@nustackdev\/ui-kit\/(.+)$/, replacement: `${KIT_SRC}/$1` },
			{ find: /^@nustackdev\/ui-kit$/, replacement: `${KIT_SRC}/index.ts` },
			// react/react-dom by absolute path, not just `dedupe`. The kit
			// source sits inside nu's own npm workspace, which has its own
			// react; two copies means every hook in a kit component throws
			// "Cannot read properties of null (reading 'useCallback')".
			// `dedupe` alone does not catch the copy zustand pulls in.
			{ find: /^react$/, replacement: REACT },
			{ find: /^react-dom$/, replacement: REACT_DOM },
			{ find: /^react\/(.*)$/, replacement: `${REACT}/$1` },
			{ find: /^react-dom\/(.*)$/, replacement: `${REACT_DOM}/$1` },
			{ find: "@", replacement: path.resolve(__dirname, "./src") },
		],
		dedupe: ["react", "react-dom", "@nustackdev/ui-core"],
	},
	build: {
		outDir: "dist",
		emptyOutDir: true,
		rollupOptions: {
			output: {
				// The prose editor's engine. Unlike Monaco this cannot be lazy:
				// a text block is live the moment the page paints, and the
				// whole point of dropping the old textarea is that there is no
				// second rendering to show while something loads. So it stays a
				// static import, but in its own chunk -- it changes on a
				// dependency bump and never on an app edit, so it caches on its
				// own clock.
				manualChunks(id: string) {
					if (id.includes("node_modules/prosemirror-")) return "prosemirror";
				},
			},
		},
	},
	server: {
		proxy: {
			"/ws": {
				target: "ws://localhost:8080",
				ws: true,
			},
			"/control": {
				target: "http://localhost:8080",
				changeOrigin: true,
			},
		},
	},
});
