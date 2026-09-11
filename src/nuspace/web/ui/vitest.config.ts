import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The kit resolves to its source here for the same reason it does in
// vite.config.ts -- ui-kit@0.1.3 has no ProseRef. Both go away together; see
// the comment there.
const KIT_SRC = path.resolve(__dirname, "../../../../../nu/packages/nustd/src/nu/ui/web/kit/src");
const REACT = path.resolve(__dirname, "node_modules/react");
const REACT_DOM = path.resolve(__dirname, "node_modules/react-dom");

export default defineConfig({
	plugins: [react()],
	resolve: {
		alias: [
			{ find: /^@nustackdev\/ui-kit\/styles$/, replacement: `${KIT_SRC}/index.css` },
			{ find: /^@nustackdev\/ui-kit\/store$/, replacement: `${KIT_SRC}/store.ts` },
			{ find: /^@nustackdev\/ui-kit\/refs$/, replacement: `${KIT_SRC}/refs/index.ts` },
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
	test: {
		server: {
			deps: {
				// Vitest externalises anything under node_modules, and an
				// externalised module is loaded by Node, which resolves its own
				// imports and never sees the aliases above. zustand is the one
				// that bites: the kit's store is a zustand store, zustand imports
				// react, and resolved from nu's workspace that is the WRONG
				// react. Inlining puts it back through vite, alias and all.
				inline: [/zustand/, /prosemirror-/, /radix-ui/],
			},
		},
		// jsdom, because the block-boundary keyboard is a DOM ordering claim
		// (see refs/pages/ProseRef.tsx) and there is no other way to check it.
		// It lays nothing out, so anything that needs real geometry --
		// `endOfTextblock`, `coordsAtPos` -- is out of reach here and is
		// covered by hand in a browser instead.
		environment: "jsdom",
		include: ["src/**/*.test.{ts,tsx}"],
	},
});
