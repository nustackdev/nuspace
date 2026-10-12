"""Fire and forget PostHog capture, no dependency beyond the stdlib.

One event is one POST on a daemon thread; the caller never waits. Every
failure (offline, host down, a bad response) is swallowed, so nothing ever
blocks or breaks because of telemetry.

Nothing is sent when telemetry is off (see :mod:`.config`), on a dev
install, or with no token. ``NUSPACE_POSTHOG_TOKEN`` and
``NUSPACE_POSTHOG_HOST`` point it at another PostHog project, eg to test.
"""

from __future__ import annotations

import json
import os
import platform
import ssl
import sys
import threading
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from . import config


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "FIRST_RUN_EVENT",
    "base_properties",
    "browser_config",
    "capture",
    "first_run",
    "posthog_host",
    "posthog_token",
]


#: The PostHog project key nu has always sent to: a public, write only token,
#: the same one the docs site ships in its client bundle.
_TOKEN = "phc_yRpWfpoMeeRM8sKMPGPEsGy8ygNHJTpsGwrsikfpRfFz"  # noqa: S105 -- public by design

#: Where events go: PostHog behind our own domain.
_HOST = "https://t.nustack.dev"

_CAPTURE_PATH = "/i/v0/e/"

#: Sent once per user, retried on every open until PostHog acks it.
FIRST_RUN_EVENT = "nuspace_first_run"

_TIMEOUT_SECONDS = 3


def posthog_token() -> str:
    """The project key, from ``NUSPACE_POSTHOG_TOKEN`` when set."""
    return os.environ.get("NUSPACE_POSTHOG_TOKEN", _TOKEN)


def posthog_host() -> str:
    """The capture host, from ``NUSPACE_POSTHOG_HOST`` when set, no trailing slash."""
    return os.environ.get("NUSPACE_POSTHOG_HOST", _HOST).rstrip("/")


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


def _post(payload: dict[str, Any], on_success: Callable[[], None] | None) -> None:
    """POST ``payload``, then ``on_success`` on a 2xx. Swallows everything."""
    request = urllib.request.Request(  # noqa: S310 -- a fixed https URL
        f"{posthog_host()}{_CAPTURE_PATH}",
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
        if 200 <= status < 300 and on_success is not None:
            on_success()
    except Exception:  # noqa: S110 -- telemetry never surfaces a failure
        pass


def _send(
    event: str, properties: dict[str, Any] | None, on_success: Callable[[], None] | None
) -> None:
    """Queue ``event`` on a daemon thread, when telemetry may send at all."""
    token = posthog_token()
    if not token or config.is_dev_install() or not config.telemetry_enabled():
        return
    payload = {
        "api_key": token,
        "event": event,
        "distinct_id": config.distinct_id(),
        "properties": {**base_properties(), **(properties or {})},
    }
    threading.Thread(target=_post, args=(payload, on_success), daemon=True).start()


def capture(event: str, properties: dict[str, Any] | None = None) -> None:
    """Send ``event`` in the background. Never raises."""
    try:
        _send(event, properties, None)
    except Exception:  # noqa: S110
        pass


def _mark_first_run() -> None:
    """Drop the marker that stops the first run event from going again."""
    marker = config.first_run_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def first_run() -> None:
    """The first run event, until PostHog acks one. Never raises.

    Fired each time the command line opens a space, until a 2xx drops the
    marker. One ``exists`` check once it has.
    """
    try:
        if config.first_run_marker().exists():
            return
        _send(FIRST_RUN_EVENT, None, _mark_first_run)
    except Exception:  # noqa: S110
        pass


def browser_config() -> dict[str, Any]:
    """What the browser is told, so its own events follow the same choice and id."""
    enabled = bool(posthog_token()) and config.telemetry_enabled() and not config.is_dev_install()
    return {
        "enabled": enabled,
        "distinct_id": config.distinct_id(),
        "posthog_token": posthog_token() if enabled else "",
        "posthog_host": posthog_host(),
        **base_properties(),
    }
