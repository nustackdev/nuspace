"""A plain model over the OpenAI wire: one call per pass, nothing remembered.

The other endpoint a chat can run against, for a model served somewhere on
the network rather than a Claude Code on the machine. One wire covers Ollama,
vLLM, OpenAI, OpenRouter and the rest, so which of them it is, is a base url.

**Stateless, and the transcript is the state.** There is no session to keep:
every call carries the system prompt and every message of the turn, and the
endpoint remembers nothing between them. That is the opposite of
:mod:`nuspace.agent.cc` and the two are deliberately not abstracted over each
other. A session and a transcript are not two implementations of one idea:
one of them is a conversation the far end is holding and the other is a
conversation this end is holding, and the only honest shared surface is the
five lines they both hand to the loop.

The system prompt goes at the head of the messages rather than in the bind,
because the wire has nowhere else to put it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.llm


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["Bot", "served_model"]


class Bot(nu.Service):
    """The chat endpoint a chat runs against."""

    chat = nustd.llm.ChatRef.method()


def served_model(
    *,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout: float = 120.0,
) -> Callable[..., nu.Nu]:
    """The endpoint a chat runs against: one model, served over the OpenAI wire.

    Args:
        base_url: where the endpoint is, e.g. ``http://red:11434`` for an
            Ollama daemon on the cluster. The path is fixed by the wire.
        model: which model to ask for. Whatever the provider calls it.
        api_key: sent as a bearer token when there is one. Ollama and vLLM
            want none.
        timeout: seconds before a call gives up. Generous, because a cold
            model is loaded off disk on the first call.

    Returns:
        A callable ``endpoint(loop, *, system)``, the same shape
        :func:`nuspace.agent.cc.claude_code` returns. ``loop`` is what to
        run once the endpoint is up, as a function of the per-pass ask.

    Notes:
        - The http client opens when the ``With`` is entered and closes when
          it exits, so the bracket has to be around the chat rather than
          around a pass even though nothing is remembered inside it.
    """

    def endpoint(loop: Callable[..., nu.Nu], *, system: str) -> nu.Nu:
        def ask(*, messages: nu.Nu) -> nu.Nu:
            """One pass's call: the system prompt, then every message of the turn."""
            framing = nu.List.of(nu.Dict.of(role=nu.Str("system"), content=nu.Str(system)))
            return Bot.chat(messages=framing + nu.List(messages))

        return nu.With(
            nustd.llm.bind(
                Bot,
                base_url=base_url,
                model=model,
                api_key=api_key,
                timeout=timeout,
            ),
            body=loop(ask),
        )

    return endpoint
