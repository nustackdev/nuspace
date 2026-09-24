"""Envs: what a run executes inside, built in the host from names.

An env is a wrap around the body and a rewrite over the loaded program::

    session = Env(wrap=lambda body: proxied_session(conn, body), label="session")

A run cannot store a lambda, so it stores specs, ``[name, *args]``, and the
host resolves them through factories registered at open (D2). The wrap runs
here, in the host, so the lambda never crosses: what crosses is the Nu it
built. The rewrite does cross, inside the body that loads the program, so it
must pickle (a class, not a closure).

Order: space-wide envs outermost, then the run's own, first outermost.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nu.context import FabricRef


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import nu
    from nu.tree import Transform


__all__ = ["Env", "EnvFactory", "KernelConfig", "KernelConfigRef", "UnknownEnvError"]


@dataclass(frozen=True)
class Env:
    """One env, built for one run.

    Args:
        wrap: ``body -> body``, run in the host at dispatch. None wraps nothing.
        rewrite: A picklable ``Nu -> Nu`` over the loaded program, applied in
            the worker after reroot. None rewrites nothing.
        label: What it is called, for reading and errors.
    """

    wrap: Callable[[nu.Nu], nu.Nu] | None = None
    rewrite: Transform | None = None
    label: str = ""


#: ``factory(*args) -> Env``, registered under a name at open.
EnvFactory = Callable[..., Env]


class UnknownEnvError(LookupError):
    """A spec names an env no factory was registered for."""


class KernelConfig:
    """What the kernel is told at open: the env registry and the space-wide envs.

    Bound on the host's context, read by dispatch. Host only: factories are
    python callables and never cross.

    Args:
        envs: Factories by name.
        space_envs: Specs applied to every run, outermost first. A bare str
            is a spec with no args.
    """

    def __init__(
        self,
        envs: Mapping[str, EnvFactory] | None = None,
        space_envs: Sequence[Sequence[str] | str] = (),
    ) -> None:
        self.envs: dict[str, EnvFactory] = dict(envs or {})
        self.space_envs: list[list[str]] = [
            [spec] if isinstance(spec, str) else list(spec) for spec in space_envs
        ]

    def build(self, spec: Sequence[str]) -> Env:
        """One spec as an env.

        Raises:
            UnknownEnvError: Nothing registered under its name.
        """
        name, *args = spec
        factory = self.envs.get(name)
        if factory is None:
            msg = f"No env registered as {name!r}"
            raise UnknownEnvError(msg)
        return factory(*args)

    def resolve(self, specs: Sequence[Sequence[str]] | None) -> list[Env]:
        """The envs a run executes inside: space-wide, then its own. Outermost first."""
        return [self.build(spec) for spec in [*self.space_envs, *(specs or [])]]


class KernelConfigRef(FabricRef):
    """The :class:`KernelConfig` bound on the context. EMPTY when none is."""

    fabric = KernelConfig
