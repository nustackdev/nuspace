import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// react/react-dom by absolute path, not just `dedupe`. The kit pulls its own
// react through the dependency graph; two copies means every hook in a kit
// component throws "Cannot read properties of null (reading 'useCallback')".
// `dedupe` alone does not catch the copy zustand pulls in.
const REACT = path.resolve(__dirname, "node_modules/react");
const REACT_DOM = path.resolve(__dirname, "node_modules/react-dom");

export default defineConfig({
	plugins: [react()],
	resolve: {
		alias: [
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
				// react, and the copy it resolves is the WRONG react. Inlining
				// puts it back through vite, alias and all.
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
