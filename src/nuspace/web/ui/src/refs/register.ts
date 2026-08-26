// Re-export the kit's official registration API for out-of-tree Refs.
//
// Nuspace-shipped refs (LensRef and friends) plug into ui-kit's runtime
// dispatch by calling this at shell boot; kit@0.1.3+ owns the maps and
// exposes the mutator. Kept as a local re-export so shell-side call sites
// (main.tsx) do not chase the kit's module layout.

export { registerRefEntry } from "@nustackdev/ui-kit";
