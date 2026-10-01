import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// react/react-dom by absolute path, not just `dedupe`. The kit pulls its own
// react through the dependency graph; two copies means every hook in a kit
// component throws "Cannot read properties of null (reading 'useCallback')".
// `dedupe` alone does not catch the copy zustand pulls in.
const REACT = path.resolve(__dirname, "node_modules/react");
const REACT_DOM = path.resolve(__dirname, "node_modules/react-dom");

// Which ui-kit to build against. By default the npm release package.json
// pins, which is what CI and every shipped wheel use. NU_KIT=local swaps in the
// kit's source from the nu checkout instead, so a kit change shows here
// without a release: `make web-build-local` / `make web-dev-local`, which also
// rebuild the kit's stylesheet first. NU_KIT_PATH points elsewhere when the
// checkout is not the sibling one. package.json and the lockfile never change.
const KIT =
	process.env.NU_KIT === "local"
		? path.resolve(process.env.NU_KIT_PATH ?? path.resolve(__dirname, "../../../../nu/pkgs/ts/ui-kit"))
		: null;
if (KIT) console.log(`ui-kit: local (${KIT})`);

/** The kit's entry points, as its package.json exports them, off its source. */
const LOCAL_KIT = KIT
	? [
			{ find: /^@nustackdev\/ui-kit$/, replacement: `${KIT}/src/index.ts` },
			{ find: /^@nustackdev\/ui-kit\/(tree|nodes)$/, replacement: `${KIT}/src/$1/index.ts` },
			{ find: /^@nustackdev\/ui-kit\/styles$/, replacement: `${KIT}/dist/styles.css` },
		]
	: [];

export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: {
		alias: [
			...LOCAL_KIT,
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
				// a text cell is live the moment the tab paints, and the
				// whole point of dropping the old textarea is that there is no
				// second rendering to show while something loads. So it stays a
				// static import, but in its own chunk -- it changes on a
				// dependency bump and never on a nuspace edit, so it caches on its
				// own clock.
				manualChunks(id: string) {
					if (id.includes("node_modules/prosemirror-")) return "prosemirror";
				},
			},
		},
	},
	server: {
		// The local kit sits outside this package; let the dev server read it.
		fs: KIT ? { allow: [__dirname, KIT] } : undefined,
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
