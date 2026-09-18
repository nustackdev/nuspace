// Reusable react that is not tied to one RefEntry.
//
// A component earns a place here by rendering and by being general enough to
// be wanted somewhere else. Every inhabitant is a ui-kit graduation candidate -
// the dot already says so in its own header.
//
// Files are kebab-case, the same as the kit's, because that is where these are
// headed. `refs/` stays PascalCase: those files are one region each, not
// primitives.
//
//   section-status-dot.tsx  the dot and the pill a Cell's state renders as
//
// Styling comes from ../design. Nothing here writes a class string of its own
// beyond the two conditional shapes the dot is drawn with.

export type { SectionStatusDotProps, SectionStatusPillProps } from "./section-status-dot";
export { SectionStatusDot, SectionStatusPill } from "./section-status-dot";
