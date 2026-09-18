"""Enables ``python -m nuspace.cli``.

The guard is load bearing, not decoration: the worker pool spawns, and a child
re-imports whatever ``__main__`` is. Without it, opening a Space forks forever.
"""

from nuspace.cli.main import main


if __name__ == "__main__":
    main()
