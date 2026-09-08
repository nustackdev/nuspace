// nuspace design layer.
//
// nuspace has no visual identity of its own. It consumes the design system at
// go/projects/nustackdev/design/ exactly the way @nustackdev/ui-kit and nudle
// do: L2/L4 semantic token names, never raw hexes.
//
// What lives here is only the vocabulary the system has not had to describe
// yet, because nudle apps are app chrome and a nuspace page is a document you
// write in: block gutter, drag handle, hover and selection affordances, the
// slash menu, and the density rule for a document surface. Plus the section
// status set, which is aliased onto the existing status hues.
//
//   tokens.css              document + section-status tokens, both themes
//   document.ts             class recipes for the document surface
//   section-status.ts       the six-state vocabulary
//   section-status-dot.tsx  the two atoms that render it
//
// Anything in here that turns out to be generic graduates to ui-kit. The
// SectionStatusDot and the gutter geometry are the current candidates.

export * from "./document";
export * from "./section-status";
export type {
	SectionStatusDotProps,
	SectionStatusPillProps,
} from "./section-status-dot";
export { SectionStatusDot, SectionStatusPill } from "./section-status-dot";
