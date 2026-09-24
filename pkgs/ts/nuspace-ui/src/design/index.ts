// nuspace design layer. Tokens and class recipes, nothing that renders.
//
// nuspace has no visual identity of its own. It consumes the design system at
// go/projects/nustackdev/design/ exactly the way @nustackdev/ui-kit and nudle
// do: L2/L4 semantic token names, never raw hexes.
//
// What lives here is only the vocabulary the system has not had to describe
// yet, because nudle apps are app chrome and a Plane the Viewer draws is a
// document you write in: block gutter, drag handle, hover and selection
// affordances, the slash menu, and the density rule for a document surface.
// Plus the section status set, which is aliased onto the existing status hues.
//
//   tokens.css         document + section-status tokens, both themes
//   shell.ts           the window frame: sidebar beside the strip of panes
//   pane.ts            one pane's top bar and its settings menu
//   document.ts        class recipes for the document surface, title included
//   rail.ts            the sidebar rail
//   resize.ts          the drag handle every resizable edge shares
//   section-status.ts  the six-state vocabulary
//
// Two rules hold this directory together:
//
//   no jsx            a recipe is a string. Anything that renders lives with
//                     the feature that renders it.
//   no wire words     nothing in here reads a field off the wire. Design only
//                     maps a name to a class string.
//
// This barrel is the import path. Nobody reaches past it into a module.
// Anything in here that turns out to be generic graduates to ui-kit.

export * from "./document";
export * from "./pane";
export * from "./rail";
export * from "./resize";
export * from "./section-status";
export * from "./shell";
