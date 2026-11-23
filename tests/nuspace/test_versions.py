"""nuspace-ui only ships at a nuspace version.

A release with UI changes bumps both to the same version; a nuspace only release
leaves the UI where it was. So the UI version never runs ahead of nuspace, and
nuspace pins exactly the UI it last shipped with. scripts/release.py does the bump.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[2]
UI = ROOT / "pkgs/ts/nuspace-ui"


def _version(path: Path) -> str:
    m = re.search(r'^version = "([^"]+)"', path.read_text(), re.M)
    assert m, path
    return m.group(1)


def _v(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in s.split("."))


def test_the_ui_version_is_one_across_its_files():
    lock = json.loads((UI / "package-lock.json").read_text())
    versions = {
        "pyproject.toml": _version(UI / "pyproject.toml"),
        "package.json": json.loads((UI / "package.json").read_text())["version"],
        "package-lock.json": lock["version"],
        'package-lock.json packages[""]': lock["packages"][""]["version"],
    }
    assert len(set(versions.values())) == 1, versions


def test_nuspace_pins_the_ui_it_ships_with():
    ui = _version(UI / "pyproject.toml")
    (pin,) = re.findall(r'"nuspace-ui>=([^"]+)"', (ROOT / "pyproject.toml").read_text())
    assert pin == ui, f"nuspace pins nuspace-ui>={pin}, the UI is at {ui}"


def test_the_ui_never_runs_ahead_of_nuspace():
    ui, nuspace = _version(UI / "pyproject.toml"), _version(ROOT / "pyproject.toml")
    assert _v(ui) <= _v(nuspace), f"nuspace-ui {ui} is ahead of nuspace {nuspace}"
