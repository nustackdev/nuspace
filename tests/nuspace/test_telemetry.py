"""Telemetry: the user's config, the opt out, the first run event, what the browser is told.

Nothing leaves the machine: the thread runs its target inline and the POST
is a stub that records what it was handed.
"""

from __future__ import annotations

import json

import pytest

from nuspace import _telemetry
from nuspace._telemetry import config, send


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


class _Inline:
    """A Thread that runs its target on ``start``, in this thread."""

    def __init__(self, target, args=(), daemon=False) -> None:
        self.target, self.args = target, args

    def start(self) -> None:
        self.target(*self.args)


class _Posted(list):
    """The POSTs made, in order. ``answer`` is what the next one gets: a status or an error."""

    answer: int | Exception = 200


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
    monkeypatch.setattr(send.threading, "Thread", _Inline)
    monkeypatch.setattr(send.urllib.request, "urlopen", urlopen)
    return sent


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
    (event,) = posted
    assert event["url"] == "https://t.nustack.dev/i/v0/e/"
    assert event["agent"].startswith("nuspace-py/")
    body = event["body"]
    assert body["event"] == send.FIRST_RUN_EVENT
    assert body["distinct_id"] == _telemetry.distinct_id()
    assert body["properties"]["product"] == "nuspace"
    assert {"nuspace_version", "nu_version", "python_version", "platform", "arch"} <= set(
        body["properties"]
    )
    assert (tmp_path / ".nuspace" / "first_run.sent").exists()
    _telemetry.first_run()
    assert len(posted) == 1


@pytest.mark.parametrize("answer", [500, OSError("offline")])
def test_first_run_retries_until_acked(tmp_path, posted, answer):
    posted.answer = answer
    _telemetry.first_run()
    _telemetry.first_run()
    assert len(posted) == 2
    assert not (tmp_path / ".nuspace" / "first_run.sent").exists()


def test_nothing_is_sent_when_off(monkeypatch, posted):
    _telemetry.set_telemetry(False)
    _telemetry.first_run()
    _telemetry.capture("x")
    monkeypatch.setenv("NUSPACE_TELEMETRY", "0")
    _telemetry.set_telemetry(True)
    _telemetry.first_run()
    _telemetry.capture("x")
    assert posted == []


def test_nothing_is_sent_from_a_dev_install(monkeypatch, posted):
    monkeypatch.setattr(config, "is_dev_install", lambda: True)
    _telemetry.first_run()
    _telemetry.capture("x")
    assert posted == []


# --- The browser -----------------------------------------------------------------


def test_browser_config_follows_the_choice(monkeypatch, posted):
    on = _telemetry.browser_config()
    assert on["enabled"] is True
    assert on["posthog_token"] == send.posthog_token()
    assert on["distinct_id"] == _telemetry.distinct_id()
    assert on["product"] == "nuspace"

    monkeypatch.setenv("NUSPACE_TELEMETRY", "off")
    off = _telemetry.browser_config()
    assert (off["enabled"], off["posthog_token"]) == (False, "")
    assert off["distinct_id"] == on["distinct_id"]


async def test_the_web_device_serves_the_browser_config():
    from nuspace.system.devices.web import device

    (route,) = device.ROUTES
    assert route.path == "/api/telemetry-config"
    response = await device.telemetry_config(None)
    body = json.loads(response.body)
    assert body["product"] == "nuspace"
    assert body["enabled"] is False  # a source checkout
