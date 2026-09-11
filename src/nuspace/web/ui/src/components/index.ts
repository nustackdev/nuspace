// Reusable react that is not tied to one RefEntry.
//
// A component earns a place here by rendering and by being wanted on more
// than one surface, or by being general enough that it would be wanted. Every
// inhabitant is a ui-kit graduation candidate - the dot already says so in its
// own header.
//
// Files are kebab-case, the same as the kit's, because that is where these are
// headed. `refs/` stays PascalCase: those files are one surface each, not
// primitives.
//
//   page-header.tsx         the page masthead: banner, icon, editable title
//   section-status-dot.tsx  the dot and the pill a section's state renders as
//   rail/                   the rail: header, row, in-row editor, roving focus
//
// Styling comes from ../design. Nothing here writes a class string of its own
// beyond the two conditional shapes the dot is drawn with.

export type { Crumb, PageIconSpec } from "./page-header";
export { DEFAULT_PAGE_ICON, PageBanner, PageHeader, PageIcon } from "./page-header";
export type { RailFocus } from "./rail";
export { RailHeader, RailRow, RailRowInput, RailRowLink, useRailFocus } from "./rail";
export type { SectionStatusDotProps, SectionStatusPillProps } from "./section-status-dot";
export { SectionStatusDot, SectionStatusPill } from "./section-status-dot";
