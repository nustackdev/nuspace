"""Shared helpers for CLI commands."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def nuspace_version() -> str:
    try:
        return version("nuspace")
    except PackageNotFoundError:
        return "0.0.0+dev"
