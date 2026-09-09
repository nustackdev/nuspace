import path from "node:path";
import { defineConfig } from "vitest/config";

// The markdown round trip is pure data: schema, parser, serializer, no DOM.
// Kept out of vite.config.ts so the build config stays about the build.
export default defineConfig({
	resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
	test: {
		environment: "node",
		include: ["src/**/*.test.ts"],
	},
});
