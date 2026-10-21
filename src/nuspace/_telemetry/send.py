"""Fire and forget PostHog capture, no dependency beyond the stdlib.

One sender thread per process, fed by a bounded queue. :func:`capture`
puts the event's name and time on the queue and returns, O(1): it never
waits, never touches the network or the disk, and drops the event when the
queue is full. The thread does the rest, the properties, the id, the opt out
and the JSON, and drains what is queued into one ``/batch/`` POST at a time. Every failure
(offline, host down, a bad response) is swallowed, so nothing ever blocks or
breaks because of telemetry. At exit the thread gets a short grace to send
what is left.

Nothing is sent when telemetry is off (see :mod:`.config`), on a dev
install, or with no token: the thread checks before each POST and drops the
batch. ``NUSPACE_POSTHOG_TOKEN`` and ``NUSPACE_POSTHOG_HOST`` point it at
another PostHog project, eg to test.
"""

from __future__ import annotations

import atexit
import json
import os
import platform
import queue
import ssl
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from . import config


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "FIRST_RUN_EVENT",
    "PREFIX",
    "base_properties",
    "capture",
    "first_run",
    "flush",
    "posthog_host",
    "posthog_token",
    "track",
]


#: The PostHog project key nu has always sent to: a public, write only token,
#: the same one the docs site ships in its client bundle.
_TOKEN = "phc_yRpWfpoMeeRM8sKMPGPEsGy8ygNHJTpsGwrsikfpRfFz"  # noqa: S105 -- public by design

#: Where events go: PostHog behind our own domain.
_HOST = "https://t.nustack.dev"

_BATCH_PATH = "/batch/"

#: What every event is sent as: the product, then what happened.
PREFIX = "nuspace_"

#: Sent once per user, retried on every open until PostHog acks it.
FIRST_RUN_EVENT = f"{PREFIX}first_run"

_TIMEOUT_SECONDS = 3

#: Events held at most; past it new ones are dropped, never waited on.
_QUEUE_CAP = 1000

#: Events in one POST at most.
_BATCH_CAP = 100

#: How long the thread lets events gather after the first before it sends.
_GATHER_SECONDS = 0.5

#: How long exit waits for what is queued.
_EXIT_GRACE_SECONDS = 2.0


def posthog_token() -> str:
    """The project key, from ``NUSPACE_POSTHOG_TOKEN`` when set."""
    return os.environ.get("NUSPACE_POSTHOG_TOKEN", _TOKEN)


def posthog_host() -> str:
    """The capture host, from ``NUSPACE_POSTHOG_HOST`` when set, no trailing slash."""
    return os.environ.get("NUSPACE_POSTHOG_HOST", _HOST).rstrip("/")


@cache
def _version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "0.0.0+dev"


def base_properties() -> dict[str, Any]:
    """What every event carries: the product, its versions, and the machine's kind."""
    v = sys.version_info
    return {
        "product": "nuspace",
        "nuspace_version": _version("nuspace"),
        "nu_version": _version("nucore"),
        "python_version": f"{v.major}.{v.minor}.{v.micro}",
        "platform": platform.system().lower(),
        "arch": platform.machine().lower(),
    }


def _ssl_context() -> ssl.SSLContext:
    """The CA bundle from certifi when importable, the platform one otherwise.

    python.org's macOS builds ship no system CA bundle, so the default
    context trusts nothing and every HTTPS POST fails verification.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _may_send() -> bool:
    """Whether anything may leave the machine right now."""
    return bool(posthog_token()) and not config.is_dev_install() and config.telemetry_enabled()


def _post(batch: list[dict[str, Any]]) -> bool:
    """POST ``batch`` in one request. Whether PostHog took it. Swallows everything."""
    payload = {"api_key": posthog_token(), "batch": batch}
    request = urllib.request.Request(  # noqa: S310 -- a fixed https URL
        f"{posthog_host()}{_BATCH_PATH}",
        data=json.dumps(payload).encode(),
        # Explicit: Cloudflare's bot rules block ``Python-urllib/x.y`` outright.
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"nuspace-py/{_version('nuspace')}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=_TIMEOUT_SECONDS, context=_ssl_context()
        ) as response:
            response.read()
            status = getattr(response, "status", 200)
    except Exception:
        return False
    return 200 <= status < 300


#: What the queue holds: the event, when it happened (unix seconds), what to
#: call once PostHog has it.
_Item = tuple[str, float, "Callable[[], None] | None"]


class _Sender:
    """The queue and the one thread that drains it, made on first use per process."""

    def __init__(self) -> None:
        self.queue: queue.Queue[_Item] = queue.Queue(maxsize=_QUEUE_CAP)
        self.thread = threading.Thread(target=self._drain, name="nuspace-telemetry", daemon=True)
        self.thread.start()

    def put(self, item: _Item) -> None:
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            pass

    def _gather(self) -> list[_Item]:
        """The next batch: wait for one event, then take what lands shortly after."""
        items = [self.queue.get()]
        deadline = time.monotonic() + _GATHER_SECONDS
        while len(items) < _BATCH_CAP:
            left = deadline - time.monotonic()
            try:
                items.append(self.queue.get(timeout=left) if left > 0 else self.queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _drain(self) -> None:
        while True:
            items = self._gather()
            try:
                self._send(items)
            except Exception:  # noqa: S110 -- telemetry never surfaces a failure
                pass
            finally:
                for _ in items:
                    self.queue.task_done()

    def _send(self, items: list[_Item]) -> None:
        if not _may_send():
            return
        base = base_properties()
        did = config.distinct_id()
        batch = [
            {
                "event": event,
                "distinct_id": did,
                "timestamp": datetime.fromtimestamp(at, timezone.utc).isoformat(),
                "properties": base,
            }
            for event, at, _ in items
        ]
        if not _post(batch):
            return
        for *_, on_success in items:
            if on_success is not None:
                on_success()

    def flush(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for the queue to empty. Whether it did."""
        deadline = time.monotonic() + timeout
        with self.queue.all_tasks_done:
            while self.queue.unfinished_tasks:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self.queue.all_tasks_done.wait(left)
        return True


_sender: _Sender | None = None
_sender_pid = 0
_sender_lock = threading.Lock()


def _the_sender() -> _Sender:
    """This process's sender, made on first ask. A forked child makes its own."""
    global _sender, _sender_pid
    pid = os.getpid()
    if _sender is None or _sender_pid != pid:
        with _sender_lock:
            if _sender is None or _sender_pid != pid:
                _sender, _sender_pid = _Sender(), pid
                atexit.register(flush, _EXIT_GRACE_SECONDS)
    return _sender


def _queue(event: str, on_success: Callable[[], None] | None) -> None:
    _the_sender().put((event, time.time(), on_success))


def capture(event: str) -> None:
    """Queue ``event`` for the sender thread. O(1), never waits, never raises."""
    try:
        _queue(event, None)
    except Exception:  # noqa: S110
        pass


def track(event: str) -> None:
    """:func:`capture` ``event`` as nuspace's own, eg ``plane_created``. The host's usage sink."""
    capture(f"{PREFIX}{event}")


def flush(timeout: float = _EXIT_GRACE_SECONDS) -> bool:
    """Wait up to ``timeout`` seconds for what is queued to go. Whether it all went.

    Gone means sent, dropped or failed: the thread is done with it.
    """
    try:
        return _sender is None or _sender_pid != os.getpid() or _sender.flush(timeout)
    except Exception:
        return False


def _mark_first_run() -> None:
    """Drop the marker that stops the first run event from going again."""
    marker = config.first_run_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def first_run() -> None:
    """The first run event, until PostHog acks one. Never raises.

    Queued each time the command line opens a space, until a 2xx drops the
    marker. One ``exists`` check once it has.
    """
    try:
        if config.first_run_marker().exists():
            return
        _queue(FIRST_RUN_EVENT, _mark_first_run)
    except Exception:  # noqa: S110
        pass
