"""Pages: the nuspace document editor ref, its driver, and section supervision.

- ``PagesRef`` / ``PagesDriver`` -- page tree + block canvas over ``Space.pages``.
- ``SectionSupervisor`` -- the five-method seam the executor implements.
- ``LocalSupervisor`` -- the v1 in-process stub behind that seam.

Section source is constructed by ``nu.prog`` and its mount fields are
enumerated by ``nuspace.exec.compile``; both are re-exported here for the
callers that used to reach into a web-local copy of them.
"""

from nuspace.exec.compile import construct_section, enumerate_ui_refs
from nuspace.web.refs.pages.pages import PagesDriver, PagesRef
from nuspace.web.refs.pages.supervise import (
    LocalSupervisor,
    SectionSpec,
    SectionStatus,
    SectionSupervisor,
)


__all__ = [
    "LocalSupervisor",
    "PagesDriver",
    "PagesRef",
    "SectionSpec",
    "SectionStatus",
    "SectionSupervisor",
    "construct_section",
    "enumerate_ui_refs",
]
