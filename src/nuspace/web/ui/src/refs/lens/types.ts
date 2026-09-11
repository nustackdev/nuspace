// The lens wire vocabulary.
//
// Two vocabularies, and keeping them apart is the whole idea:
//
//   KIND   the structural kind of a row - what kind of column it opens.
//          shape | mapping | sequence | leaf | unknown. Comes off the wire
//          as `entry.kind`.
//   VTYPE  the type of the VALUE a row holds. str | int | float | bool |
//          bytes | none | empty | invalid | error | list | dict | ref.
//          Comes off the wire as `entry.vtype`.
//
// A row shows the vtype glyph when it has a value and the kind glyph when it
// does not (a shape slot, a dict key). That is what makes a string, an int, a
// nested shape, an unset slot and a sentinel tell themselves apart at a
// glance without a legend.
//
// These are wire words, so they live with the ref. The design layer only ever
// sees the type name and hands back a class string - see design/lens.ts.

import {
	Binary,
	Box,
	Braces,
	Brackets,
	CircleDashed,
	CircleSlash,
	Hash,
	type LucideIcon,
	ToggleLeft,
	TriangleAlert,
	Type,
} from "lucide-react";

export type Kind = "shape" | "mapping" | "sequence" | "leaf" | "unknown";

const KIND_ICON: Record<string, LucideIcon> = {
	shape: Box,
	mapping: Braces,
	sequence: Brackets,
	leaf: Type,
	unknown: CircleSlash,
};

/** Human label for a column header. `mapping`/`sequence` are wire words. */
const KIND_LABEL: Record<string, string> = {
	shape: "shape",
	mapping: "dict",
	sequence: "list",
	leaf: "value",
	unknown: "unknown",
};

const VTYPE_ICON: Record<string, LucideIcon> = {
	str: Type,
	int: Hash,
	float: Hash,
	bool: ToggleLeft,
	bytes: Binary,
	none: CircleSlash,
	empty: CircleDashed,
	invalid: TriangleAlert,
	error: TriangleAlert,
	list: Brackets,
	dict: Braces,
};

export function kindLabel(kind: string): string {
	return KIND_LABEL[kind] ?? kind;
}

/**
 * The glyph for one row. Value type wins when the row holds a value; the
 * structural kind carries it otherwise (a shape slot has not been read yet,
 * a dict key is a door and not a value).
 */
export function rowIcon(kind: string, vtype: string): LucideIcon {
	return VTYPE_ICON[vtype] ?? KIND_ICON[kind] ?? KIND_ICON.unknown;
}

export function kindIcon(kind: string): LucideIcon {
	return KIND_ICON[kind] ?? KIND_ICON.unknown;
}

/** The word a sentinel renders as, inside its chip. */
export const VTYPE_SENTINEL_LABEL: Record<string, string> = {
	empty: "empty",
	none: "none",
	invalid: "invalid",
	error: "error",
};
