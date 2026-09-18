/// <reference types="vite/client" />

// Ambient shim: ui-kit ships an ./styles subpath that resolves to a CSS
// file. TS doesn't type CSS imports, so declare the module explicitly.
declare module "@nustackdev/ui-kit/styles";
