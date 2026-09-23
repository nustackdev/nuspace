"""Enables ``python -m nuspace.host.cli``.

The guard is load bearing: workers are spawned, and a child re-imports
whatever ``__main__`` is. Without it, opening a space forks forever.
"""

from .main import main


if __name__ == "__main__":
    main()
