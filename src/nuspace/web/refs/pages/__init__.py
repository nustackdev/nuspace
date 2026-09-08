"""Pages: the nuspace document editor ref, its driver, and section supervision.

- ``PagesRef`` / ``PagesDriver`` -- page tree + block canvas over ``Space.pages``.
- ``SectionSupervisor`` -- the five-method seam the executor implements.
- ``LocalSupervisor`` -- the v1 in-process stub behind that seam.
"""

from nuspace.web.refs.pages.compile import enumerate_ui_refs, parse_snippet
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
    "enumerate_ui_refs",
    "parse_snippet",
]
