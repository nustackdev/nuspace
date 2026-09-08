"""Concrete :class:`~nuspace.exec.supervisor.UiHost` implementations.

The supervisor does not know what a browser is. It hands every frame a
section produces to a host, and asks the host for round-trip reads. Two
hosts live here:

- :class:`SessionHost` wraps any ``nu.ui.core.Session`` -- in practice
  the one websocket session that owns a browser connection. N workers
  share it, and frames stay distinguishable because ui paths are
  section-prefixed, which is the same rule that decides mounting.
- :class:`LoopbackHost` records everything and lets a test answer reads
  and inject notifies. Enough to exercise the whole channel without a
  browser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.ui.core.protocol import Frame
    from nu.ui.core.session import Session


__all__ = ["LoopbackHost", "SessionHost"]


class SessionHost:
    """Route section frames onto one browser session.

    Frame routing when N workers share one connection needs no envelope:
    every ui ref a section owns is named under its own path prefix, so a
    frame's ``ref`` already says which section it came from and which
    browser slice it lands in.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def send(self, page_id: str, section_id: str, frame: Frame) -> None:
        """Ship a section's frame to the browser."""
        del page_id, section_id
        await self._session.send(frame)

    async def aread(self, page_id: str, section_id: str, path: str) -> Any:  # noqa: ANN401
        """Round-trip a read to the browser."""
        del page_id, section_id
        return await self._session.aread(path)


class LoopbackHost:
    """In-memory host: records frames, serves reads from a dict."""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.frames: list[tuple[str, str, Frame]] = []
        self.values: dict[str, Any] = dict(values or {})
        self.on_frame: Callable[[str, str, Frame], None] | None = None

    async def send(self, page_id: str, section_id: str, frame: Frame) -> None:
        """Record a frame and fire the optional hook."""
        self.frames.append((page_id, section_id, frame))
        if self.on_frame is not None:
            self.on_frame(page_id, section_id, frame)

    async def aread(self, page_id: str, section_id: str, path: str) -> Any:  # noqa: ANN401
        """Answer a read out of ``values``."""
        del page_id, section_id
        return self.values.get(path)

    def writes(self, ref: str | None = None) -> list[Any]:
        """Payloads of every ``write`` frame, optionally filtered by ref."""
        return [
            f.payload
            for _, _, f in self.frames
            if f.op == "write" and (ref is None or f.ref == ref)
        ]
