// The page masthead.
//
// Four parts, in the order you read them: the trail that says where you are,
// a generated banner, the page icon, and the title. The title is the only
// interactive one, and it is interactive by being editable, not by being a
// button that opens a dialog.
//
// Everything visual lives in ./header.ts. This file is composition and the
// one piece of real behaviour: capturing a rename from a contenteditable
// heading without letting React and the browser fight over the text node.
//
// Not in scope for v1: an icon picker and a cover picker. Both are structured
// for - `PageIcon` takes a spec and `PageBanner` keeps a seed - so adding
// them later is a new trigger and a new spec variant, not a rewrite.

import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
	cn,
	headingVariants,
} from "@nustackdev/ui-kit";
import type React from "react";
import { Fragment, useCallback, useEffect, useRef } from "react";

import {
	docBanner,
	docBannerFadeStyle,
	docBannerGridStyle,
	docBannerLayer,
	docBannerTrail,
	docBannerWashStyle,
	docMasthead,
	docMastheadColumn,
	docPageIcon,
	docPageIconGlyph,
	docTitle,
} from "./header";

/* ============================== page icon ================================ */

/**
 * What a page's icon is. v1 only ever constructs `{ kind: "default" }`; the
 * other two exist so the picker that lands later has somewhere to write to
 * and so nothing downstream has to change shape when it does.
 */
export type PageIconSpec =
	| { kind: "default" }
	| { kind: "emoji"; char: string }
	| { kind: "image"; src: string };

export const DEFAULT_PAGE_ICON: PageIconSpec = { kind: "default" };

/**
 * The default glyph: a page. Drawn rather than imported, because the icon is
 * the one mark on this surface that carries meaning, and direction.md is
 * explicit that meaning does not travel on a lucide glyph here. Hairline,
 * rx 3, the same grammar as the banner it sits on.
 */
function DefaultPageGlyph({ className }: { className?: string }) {
	return (
		<svg
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth={1.25}
			vectorEffect="non-scaling-stroke"
			aria-hidden="true"
			className={className}
		>
			<path d="M5.5 3.5h8.5l4.5 4.5v12.5h-13z" strokeLinejoin="round" />
			<path d="M14 3.5V8h4.5" strokeLinejoin="round" />
			<path d="M8.5 12h7M8.5 15.5h7M8.5 19h4" strokeLinecap="round" />
		</svg>
	);
}

export function PageIcon({ icon = DEFAULT_PAGE_ICON }: { icon?: PageIconSpec }) {
	// A picker will make this frame a trigger. Until then it is decoration and
	// says so: no button, no hover, nothing to click that does nothing.
	return (
		<div className={docPageIcon} data-slot="page-icon" aria-hidden="true">
			{icon.kind === "emoji" ? (
				<span className="text-2xl leading-none">{icon.char}</span>
			) : icon.kind === "image" ? (
				<img src={icon.src} alt="" className="size-full rounded-lg object-cover" />
			) : (
				<DefaultPageGlyph className={docPageIconGlyph} />
			)}
		</div>
	);
}

/* ============================== banner =================================== */

/**
 * The banner. A pattern, not a picture: a dot-grid substrate, one accent
 * wash, and a fade into the canvas so the cover ends without a horizon.
 *
 * Deliberately the same on every page. A per-page generated mark was tried
 * and read as noise: the masthead's job is to frame the title, and anything
 * with structure in it competes with the document underneath.
 *
 * Swap this body for an <img> when covers become uploadable; `seed` is kept
 * so a per-page cover has somewhere to key off.
 */
export function PageBanner({ children }: { seed?: string; children?: React.ReactNode }) {
	return (
		<div className={docBanner} data-slot="page-banner">
			<div className={docBannerLayer} style={docBannerGridStyle} />
			<div className={docBannerLayer} style={docBannerWashStyle} />
			<div className={docBannerLayer} style={docBannerFadeStyle} />
			{children}
		</div>
	);
}

/* ============================== trail ==================================== */

export type Crumb = {
	label: string;
	href: string;
	onClick: (e: React.MouseEvent<HTMLElement>) => void;
};

function Trail({ crumbs }: { crumbs: Crumb[] }) {
	if (crumbs.length === 0) return null;
	return (
		<Breadcrumb className={docBannerTrail}>
			<BreadcrumbList className="flex-nowrap text-xs">
				{crumbs.map((c, i) => (
					<Fragment key={c.href}>
						{i > 0 ? <BreadcrumbSeparator /> : null}
						<BreadcrumbItem className="min-w-0">
							<BreadcrumbLink href={c.href} onClick={c.onClick} className="truncate">
								{c.label}
							</BreadcrumbLink>
						</BreadcrumbItem>
					</Fragment>
				))}
			</BreadcrumbList>
		</Breadcrumb>
	);
}

/* ============================== title ==================================== */

/**
 * The title, as an always-editable `h1`.
 *
 * The contract with the caller is unchanged: `onCommit(title)` is what used
 * to fire behind `window.prompt`, and it still ships
 * `{op: "on_page_rename", path, title}`. Only the capture changed.
 *
 * Two rules make contenteditable behave under React:
 *
 *  1. React never owns the text. The element renders empty and an effect
 *     writes `textContent`, and only when the element is not focused. React
 *     re-rendering mid-edit would otherwise reset the caret to position 0 on
 *     every keystroke that arrived alongside a store update.
 *  2. Escape restores from a ref captured at focus time, not from props.
 *     Props may have moved underneath the edit (someone else renamed the page
 *     while you were typing) and cancel means "undo what I typed".
 */
function EditableTitle({
	value,
	placeholder,
	onCommit,
}: {
	value: string;
	placeholder: string;
	onCommit: (title: string) => void;
}) {
	const ref = useRef<HTMLHeadingElement>(null);
	const entry = useRef(value);

	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		if (document.activeElement === el) return;
		if (el.textContent !== value) el.textContent = value;
	}, [value]);

	const commit = useCallback(() => {
		const el = ref.current;
		if (!el) return;
		// A title is one line. Anything pasted with newlines collapses.
		const next = (el.textContent ?? "").replace(/\s+/g, " ").trim();
		if (next === value) {
			el.textContent = value;
			return;
		}
		if (next.length === 0) {
			// Empty is not a rename, it is a mistake. Restore and let the
			// placeholder do its job only for pages that never had a title.
			el.textContent = value;
			return;
		}
		el.textContent = next;
		onCommit(next);
	}, [onCommit, value]);

	const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLHeadingElement>) => {
		if (e.key === "Enter") {
			e.preventDefault();
			e.currentTarget.blur(); // blur commits
			return;
		}
		if (e.key === "Escape") {
			e.preventDefault();
			const el = e.currentTarget;
			el.textContent = entry.current;
			el.blur();
		}
	}, []);

	return (
		// No `role="textbox"`: `contenteditable` already exposes this node as
		// editable text, and an explicit role would strip the heading semantics
		// that are the whole reason this is an h1.
		<h1
			ref={ref}
			contentEditable
			suppressContentEditableWarning
			spellCheck={false}
			aria-label="Page title"
			data-placeholder={placeholder}
			className={cn(headingVariants({ size: "display" }), docTitle)}
			onFocus={(e) => {
				entry.current = e.currentTarget.textContent ?? "";
			}}
			onKeyDown={onKeyDown}
			onBlur={commit}
			// Newlines and rich paste are not titles.
			onPaste={(e) => {
				e.preventDefault();
				const text = e.clipboardData.getData("text/plain").replace(/\s+/g, " ");
				document.execCommand("insertText", false, text);
			}}
		/>
	);
}

/* ============================== masthead ================================= */

export function PageHeader({
	title,
	seed,
	crumbs,
	placeholder,
	icon,
	onRename,
}: {
	title: string;
	/** Stable per page; the banner's mark is a function of it. */
	seed: string;
	crumbs: Crumb[];
	placeholder: string;
	icon?: PageIconSpec;
	onRename: (title: string) => void;
}) {
	return (
		<header className={docMasthead}>
			<PageBanner seed={seed}>
				<Trail crumbs={crumbs} />
			</PageBanner>
			<div className={docMastheadColumn}>
				<PageIcon icon={icon} />
				<EditableTitle value={title} placeholder={placeholder} onCommit={onRename} />
			</div>
		</header>
	);
}
