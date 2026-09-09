import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	build: {
		outDir: "dist",
		emptyOutDir: true,
		rollupOptions: {
			output: {
				// The prose island's engine. Unlike Monaco this cannot be lazy:
				// a prose block is live the moment the page paints, and the
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
