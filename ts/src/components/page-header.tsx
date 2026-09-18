// The page head.
//
// Two parts: the trail that says where you are, and the page's own name. A
// page opens on the trail, then on blank air, then on its title, which is what
// a document with no cover looks like everywhere people already write. There
// was a masthead here -- a generated banner and a page icon above the title --
// and both were chrome about a document rather than the document, so they are
// gone rather than tuned. The trail stayed because it is the only thing up
// here that answers a question.
//
// Everything visual lives in ../design/document.ts. This file is composition
// and the one piece of real behaviour: capturing a rename from a
// contenteditable heading without letting React and the browser fight over the
// text node.

import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@nustackdev/ui-kit";
import type React from "react";
import { Fragment, useCallback, useEffect, useRef } from "react";

import { docTitle, docTitleHead, docTrail } from "../design";

/* ============================== trail ==================================== */

export type Crumb = {
	label: string;
	href: string;
	onClick: (e: React.MouseEvent<HTMLElement>) => void;
};

function Trail({ crumbs }: { crumbs: Crumb[] }) {
	if (crumbs.length === 0) return null;
	return (
		<Breadcrumb className={docTrail}>
			<BreadcrumbList className="flex-nowrap text-xs">
				{crumbs.map((c, i) => (
					<Fragment key={c.href}>
						{i > 0 ? <BreadcrumbSeparator /> : null}
						<BreadcrumbItem className="min-w-0">
							{/* The last crumb is where you already are, so it is a
							    position and not a destination: text, not a link. */}
							{i === crumbs.length - 1 ? (
								<BreadcrumbPage className="truncate">{c.label}</BreadcrumbPage>
							) : (
								<BreadcrumbLink href={c.href} onClick={c.onClick} className="truncate">
									{c.label}
								</BreadcrumbLink>
							)}
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
			className={docTitle}
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

/* ============================== head ===================================== */

export function PageHeader({
	title,
	crumbs,
	placeholder,
	onRename,
}: {
	title: string;
	crumbs: Crumb[];
	placeholder: string;
	onRename: (title: string) => void;
}) {
	return (
		<header className={docTitleHead}>
			<Trail crumbs={crumbs} />
			<EditableTitle value={title} placeholder={placeholder} onCommit={onRename} />
		</header>
	);
}
