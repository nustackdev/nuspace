"""Bump a nuspace release, and nuspace-ui to the same version when the UI changed.

Versioning rule: nuspace-ui only ever ships at a nuspace version.

    nuspace | nuspace-ui
    1.0       1.0        both released, the UI changed
    1.1       1.0        nuspace only, the UI did not change
    1.2       1.2        both again

So the UI version always names the nuspace release that last carried a UI change,
and nuspace pins `nuspace-ui>=` exactly that version. tests/nuspace/test_versions.py
and both publish workflows hold this.

Usage (from the repo root, with the project venv):

    .venv/bin/python scripts/release.py 0.8.2           # bump files + changelog, nothing else
    .venv/bin/python scripts/release.py 0.8.2 --ui      # force a UI release
    .venv/bin/python scripts/release.py 0.8.2 --no-ui   # force nuspace only

The UI counts as changed when anything under pkgs/ts/nuspace-ui differs from the
last `nuspace-ui@*` tag. The script only edits files; then commit, push, and tag
`nuspace-ui@X.Y.Z` first (when bumped, wait for its publish run) and `nuspace@X.Y.Z`.
"""

# ruff: noqa: D103, S101, S603, S607, T201 -- a release CLI: prints, shells out to git

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "pkgs/ts/nuspace-ui"
UI_REL = "pkgs/ts/nuspace-ui"
PYPROJECT = ROOT / "pyproject.toml"
UI_PYPROJECT = UI / "pyproject.toml"
UI_PACKAGE = UI / "package.json"
UI_LOCK = UI / "package-lock.json"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r'^version = "([^"]+)"', re.M)


def parse(v: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"not an X.Y.Z version: {v}")
    return tuple(int(p) for p in v.split("."))


def git(*args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if check and out.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{out.stderr}")
    return out.stdout.strip()


def pyproject_version(path: Path) -> str:
    m = VERSION_RE.search(path.read_text())
    assert m, path
    return m.group(1)


def last_ui_tag() -> str | None:
    tags = git("tag", "-l", "nuspace-ui@*", "--sort=-v:refname").splitlines()
    return tags[0] if tags else None


def ui_changed() -> bool:
    tag = last_ui_tag()
    if tag is None:
        return True
    return bool(git("diff", "--name-only", tag, "HEAD", "--", UI_REL))


def sub_once(path: Path, pattern: str, repl: str, count: int = 1, flags: int = re.M) -> None:
    text, n = re.subn(pattern, repl, path.read_text(), count=count, flags=flags)
    if n != count:
        sys.exit(f"{path.relative_to(ROOT)}: expected {count} match(es) for {pattern!r}, got {n}")
    path.write_text(text)


def bump_ui(version: str) -> None:
    sub_once(UI_PYPROJECT, r'^version = "[^"]+"', f'version = "{version}"')
    # Text edits, not a json round trip, so npm's formatting stays untouched.
    # package.json carries one top level version (one tab deep); the lockfile
    # two, its root and packages[""], each right after `"name": "nuspace-ui"`.
    sub_once(UI_PACKAGE, r'^(\t"version": )"[^"]+"', rf'\g<1>"{version}"')
    sub_once(
        UI_LOCK, r'("name": "nuspace-ui",\s*"version": )"[^"]+"', rf'\g<1>"{version}"', count=2
    )
    for path in (UI_PACKAGE, UI_LOCK):
        json.loads(path.read_text())  # still valid
    sub_once(PYPROJECT, r'"nuspace-ui>=[^"]+"', f'"nuspace-ui>={version}"')


def bump_changelog(version: str, ui_version: str, with_ui: bool) -> None:
    today = dt.date.today().isoformat()
    title = f"Release nuspace {version}" + (f", nuspace-ui {version}" if with_ui else "")
    sub_once(CHANGELOG, r"^(- \*\*nuspace\*\* .*— )\S+$", rf"\g<1>{version}")
    sub_once(CHANGELOG, r"^(- \*\*nuspace-ui\*\* .*— )\S+$", rf"\g<1>{ui_version}")
    sub_once(CHANGELOG, r"^## Unreleased\n\n", f"## {version} - {today}\n\n- {title}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("version")
    ui = ap.add_mutually_exclusive_group()
    ui.add_argument(
        "--ui", dest="ui", action="store_true", default=None, help="release nuspace-ui too"
    )
    ui.add_argument("--no-ui", dest="ui", action="store_false", help="release nuspace only")
    args = ap.parse_args()

    if git("status", "--porcelain"):
        sys.exit("working tree is not clean, commit or stash first")
    if git("branch", "--show-current") != "main":
        sys.exit("releases go from main")
    git("fetch", "-q", "--tags", "origin")

    current = pyproject_version(PYPROJECT)
    if parse(args.version) <= parse(current):
        sys.exit(f"{args.version} is not above the current nuspace {current}")
    if "## Unreleased" not in CHANGELOG.read_text():
        sys.exit("CHANGELOG.md has no `## Unreleased` section")

    with_ui = ui_changed() if args.ui is None else args.ui
    ui_version = args.version if with_ui else pyproject_version(UI_PYPROJECT)

    sub_once(PYPROJECT, r'^version = "[^"]+"', f'version = "{args.version}"')
    if with_ui:
        bump_ui(args.version)
    bump_changelog(args.version, ui_version, with_ui)

    print(f"nuspace {current} -> {args.version}")
    print(
        f"nuspace-ui {'-> ' + args.version if with_ui else 'stays at ' + ui_version} "
        f"({'changed' if with_ui else 'unchanged'} since {last_ui_tag()})"
    )

    print("files bumped, nothing committed. review `git diff`; `git checkout .` undoes it")


if __name__ == "__main__":
    main()
