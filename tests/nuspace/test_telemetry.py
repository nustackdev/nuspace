"""Telemetry: the config, the opt out, the sender thread, the host's usage, the browser's route.

Nothing leaves the machine: the sender thread is real, the POST is a stub
that records what it was handed, and each test flushes before it looks.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

import nu
from nuspace import _telemetry
from nuspace._telemetry import config, send
from nuspace.system.usage import Track, Usage


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("NUSPACE_TELEMETRY", "NUSPACE_POSTHOG_TOKEN", "NUSPACE_POSTHOG_HOST"):
        monkeypatch.delenv(name, raising=False)


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b"{}"


class _Posted(list):
    """The POSTs made, in order. ``answer`` is what the next one gets: a status or an error."""

    answer: int | Exception = 200

    def events(self) -> list[dict]:
        """Every event sent, flushed first, across POSTs in order."""
        assert send.flush(5)
        return [event for post in self for event in post["body"]["batch"]]


@pytest.fixture
def posted(monkeypatch):
    """A real install, every POST recorded and answered with ``posted.answer``."""
    sent = _Posted()

    def urlopen(request, timeout, context):
        sent.append(
            {
                "url": request.full_url,
                "agent": request.get_header("User-agent"),
                "body": json.loads(request.data),
            }
        )
        if isinstance(sent.answer, Exception):
            raise sent.answer
        return _Response(sent.answer)

    monkeypatch.setattr(config, "is_dev_install", lambda: False)
    monkeypatch.setattr(send, "_GATHER_SECONDS", 0.05)
    monkeypatch.setattr(send.urllib.request, "urlopen", urlopen)
    yield sent
    send.flush(5)


# --- The config ------------------------------------------------------------------


def test_config_is_made_on_first_ask_with_a_stable_id(tmp_path):
    assert not (tmp_path / ".nuspace").exists()
    did = _telemetry.distinct_id()
    assert json.loads((tmp_path / ".nuspace" / "config.json").read_text()) == {
        "telemetry": True,
        "distinct_id": did,
    }
    assert _telemetry.distinct_id() == did
    assert _telemetry.telemetry_enabled() is True


def test_set_telemetry_keeps_the_id():
    did = _telemetry.distinct_id()
    _telemetry.set_telemetry(False)
    assert _telemetry.telemetry_enabled() is False
    assert _telemetry.distinct_id() == did


def test_a_broken_config_is_remade(tmp_path):
    (tmp_path / ".nuspace").mkdir()
    (tmp_path / ".nuspace" / "config.json").write_text("not json")
    assert _telemetry.telemetry_enabled() is True
    assert _telemetry.distinct_id()


@pytest.mark.parametrize("value", ["0", "false", "off", "OFF", " no "])
def test_the_environment_turns_it_off(monkeypatch, value):
    _telemetry.set_telemetry(True)
    monkeypatch.setenv("NUSPACE_TELEMETRY", value)
    assert _telemetry.env_override() is True
    assert _telemetry.telemetry_enabled() is False


@pytest.mark.parametrize("value", ["1", "on", ""])
def test_the_environment_never_turns_it_on(monkeypatch, value):
    _telemetry.set_telemetry(False)
    monkeypatch.setenv("NUSPACE_TELEMETRY", value)
    assert _telemetry.telemetry_enabled() is False


def test_a_source_checkout_is_a_dev_install():
    assert _telemetry.is_dev_install() is True


# --- Sending ---------------------------------------------------------------------


def test_first_run_sends_once_acked(tmp_path, posted):
    _telemetry.first_run()
    (event,) = posted.events()
    (post,) = posted
    assert post["url"] == "https://t.nustack.dev/batch/"
    assert post["agent"].startswith("nuspace-py/")
    assert post["body"]["api_key"] == send.posthog_token()
    assert event["event"] == send.FIRST_RUN_EVENT
    assert event["distinct_id"] == _telemetry.distinct_id()
    assert event["timestamp"]
    assert event["properties"]["product"] == "nuspace"
    assert {"nuspace_version", "nu_version", "python_version", "platform", "arch"} <= set(
        event["properties"]
    )
    assert (tmp_path / ".nuspace" / "first_run.sent").exists()
    _telemetry.first_run()
    assert len(posted.events()) == 1


@pytest.mark.parametrize("answer", [500, OSError("offline")])
def test_first_run_retries_until_acked(tmp_path, posted, answer):
    posted.answer = answer
    _telemetry.first_run()
    posted.events()
    _telemetry.first_run()
    assert len(posted.events()) == 2
    assert not (tmp_path / ".nuspace" / "first_run.sent").exists()


def test_events_close_together_go_in_one_post(posted):
    for n in range(5):
        _telemetry.capture(f"x{n}")
    assert [e["event"] for e in posted.events()] == ["x0", "x1", "x2", "x3", "x4"]
    assert len(posted) == 1


def test_an_event_carries_the_machine_and_nothing_else(posted):
    _telemetry.track("plane_created")
    (event,) = posted.events()
    assert event["event"] == "nuspace_plane_created"
    assert event["properties"] == send.base_properties()


def test_capture_never_waits_on_the_network(monkeypatch, posted):
    gate = threading.Event()
    monkeypatch.setattr(send, "_post", lambda batch: gate.wait(5))
    started = time.monotonic()
    for _ in range(send._QUEUE_CAP * 2):  # past the cap: dropped, not waited on
        _telemetry.capture("x")
    assert time.monotonic() - started < 1
    gate.set()


def test_nothing_is_sent_when_off(monkeypatch, posted):
    _telemetry.set_telemetry(False)
    _telemetry.first_run()
    _telemetry.capture("x")
    assert posted.events() == []
    monkeypatch.setenv("NUSPACE_TELEMETRY", "0")
    _telemetry.set_telemetry(True)
    _telemetry.first_run()
    _telemetry.capture("x")
    assert posted.events() == []


def test_nothing_is_sent_from_a_dev_install(monkeypatch, posted):
    monkeypatch.setattr(config, "is_dev_install", lambda: True)
    _telemetry.first_run()
    _telemetry.capture("x")
    assert posted.events() == []


# --- The host's usage and the browser's route ------------------------------------


def test_a_sink_that_raises_breaks_nothing():
    def sink(event):
        raise RuntimeError

    Usage(sink=sink).track("x")


def test_track_tells_the_bound_usage_and_nobody_otherwise():
    told = []
    track = Track("plane_created") >> Track("cell_removed")
    nu.run(track)
    assert told == []
    nu.run(nu.Provide(Usage, {"sink": told.append}, track))
    assert told == ["plane_created", "cell_removed"]


async def test_the_web_device_queues_space_loaded(posted):
    from nuspace.system.devices.web import device

    (route,) = device.ROUTES
    assert (route.path, route.methods >= {"POST"}) == ("/api/telemetry/space-loaded", True)
    response = await device.space_loaded(None)
    assert response.status_code == 204
    assert [e["event"] for e in posted.events()] == ["nuspace_space_loaded"]
