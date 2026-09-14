// nuspace design layer. Tokens and class recipes, nothing that renders.
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
//   tokens.css         document + section-status tokens, both themes
//   editor.css         prose editor internals
//   lens.css           lens surface tokens
//   shell.ts           the window frame and its top strip
//   document.ts        class recipes for the document surface
//   header.ts          the page masthead
//   rail.ts            the rail, shared by the pages and apps surfaces
//   apps.ts            the apps canvas
//   chat.ts            the agent sidebar, pinned on the shell
//   lens.ts            the lens surface
//   section-status.ts  the six-state vocabulary
//
// Two rules hold this directory together:
//
//   no jsx            a recipe is a string. Anything that renders lives in
//                     ../components or with its ref. That is why
//                     page-header.tsx and section-status-dot.tsx are not here.
//   no wire words     nothing in here reads a field off the wire. The lens
//                     kind/vtype vocabulary lives in ../refs/lens/types.ts;
//                     design only maps a type name to a class string.
//
// This barrel is the import path. Nobody reaches past it into a module.
// Anything in here that turns out to be generic graduates to ui-kit.

export * from "./apps";
export * from "./chat";
export * from "./document";
export * from "./header";
export * from "./lens";
export * from "./rail";
export * from "./section-status";
export * from "./shell";
