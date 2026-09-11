"""Pages: the nuspace document editor.

    ref.py            the wire handle, and nothing else
    ops.py            one ref per op; the path is the dispatch
    interactions/     page.py  block.py  ship.py
    view.py           one connection's cursor, supervisor and dirty flags
    store.py          walking the page substrate
    control.py        composes the above into one per-connection program
    supervise.py      the five-method section supervisor seam

Section source is constructed by ``nu.prog`` and its mount fields are
enumerated by ``nuspace.exec.compile``; both are re-exported here for the
callers that used to reach into a web-local copy of them.
"""

from nuspace.exec.compile import construct_section, enumerate_ui_refs
from nuspace.web.refs.pages.control import PagesDriver
from nuspace.web.refs.pages.ref import PagesRef
from nuspace.web.refs.pages.supervise import (
    LocalSupervisor,
    SectionSpec,
    SectionStatus,
    SectionSupervisor,
)
from nuspace.web.refs.pages.view import Cursor, View


__all__ = [
    "Cursor",
    "LocalSupervisor",
    "PagesDriver",
    "PagesRef",
    "SectionSpec",
    "SectionStatus",
    "SectionSupervisor",
    "View",
    "construct_section",
    "enumerate_ui_refs",
]
