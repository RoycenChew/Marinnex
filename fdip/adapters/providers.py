"""The model stack: three modes, one assembly order.

```
GovernedLLM(CachedLLM(client))
```

The cache sits **inside** the governor so a replayed answer is not charged
against the ceiling. Getting this backwards was a real defect in the benchmark:
the governor refused a cached call because the cache reported zero cost and the
guard read that as an unpriced call.

`FDIP_EXTRACT_THINKING` is applied to the **client**, not to a wrapper. Neither
`CachedLLM` nor `GovernedLLM` forwards an attribute write, so setting
`extra_body` on the governed model sets a dead attribute and leaves reasoning on
-- the exact bug that made the benchmark's option (c) measure as option (a), at
73,241 output tokens against the 23,552 it should have produced. `ThinkingSwitch`
therefore holds the client it mutates.

Modes:

* `mock` -- `ScriptedLLM` driven by fixtures. No network, no spend. The default.
* `recorded` -- the cache only. A miss is an error rather than a request, so a
  test cannot start spending by accident.
* `live` -- a real DeepSeek call, governed by the monthly ceiling.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fdip.config import Settings

PLAIN_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}}
"""DeepSeek's switch for turning reasoning off. Measured on 30 documents: 4.4x
fewer output tokens and 1.7x lower latency, at the cost of 1.7 points of field
accuracy, which is why `off` is not the default."""


class ProviderUnavailable(RuntimeError):
    """A recorded-mode miss, or a live mode with nothing configured."""


class ThinkingSwitch:
    """Reasoning off for the first attempt of a document, on for any repair.

    The bet: most documents are easy, and the few that fail validation are the
    ones worth thinking about. `start_document()` is not optional -- without it
    the second document inherits the first's attempt count and runs with
    reasoning on for the rest of the batch.
    """

    def __init__(self, llm: Any, client: Any, mode: str) -> None:
        self._llm = llm
        self._client = client
        """The object the request is actually built from. See the module
        docstring: a wrapper here silently does nothing."""
        self._mode = mode
        self._attempt = 0

    @property
    def model_version(self) -> str:
        """Distinct per mode, so two settings cannot share cache entries."""
        base = str(getattr(self._llm, "model_version", "") or "llm")
        return "%s:thinking=%s" % (base, self._mode)

    def start_document(self) -> None:
        self._attempt = 0

    def _body_for_attempt(self) -> dict[str, Any]:
        if self._mode == "off":
            return dict(PLAIN_BODY)
        if self._mode == "repair":
            return dict(PLAIN_BODY) if self._attempt == 1 else {}
        return {}

    def complete(self, messages: Sequence[Any], temperature: float = 0.0,
                 max_tokens: int | None = None) -> Any:
        self._attempt += 1
        if hasattr(self._client, "extra_body"):
            self._client.extra_body = self._body_for_attempt()
        return self._llm.complete(messages, temperature, max_tokens)


@dataclass
class ModelStack:
    llm: Any
    """What the pipeline calls. Already governed, cached and switched."""
    cache: Any
    client: Any
    mode: str
    provider_name: str
    model: str

    def start_document(self) -> None:
        start = getattr(self.llm, "start_document", None)
        if callable(start):
            start()

    @property
    def spent_usd(self) -> float:
        state = getattr(self.llm, "state", None)
        return float(getattr(state, "cost_usd", 0.0) or 0.0)


def _deepseek_prices() -> Any:
    """DeepSeek's prices, read 2026-10-07, priced at **peak**.

    Peak is the exception rather than the rule: the peak rate applies only from
    01:00-04:00 and 06:00-10:00 UTC on weekdays, so the real bill is usually
    about half of what this reports. Over-estimating is the safe direction for a
    ceiling and the honest direction for a cost claim.

    Without a price book `Usage.cost_usd` stays zero and the monthly ceiling can
    never bind, which the toolkit's governor now refuses rather than pretending.
    """
    from toolkit.provider import ModelPrice, PriceBook

    source = "api-docs.deepseek.com/quick_start/pricing, read 2026-10-07; peak rate"
    return PriceBook(
        prices={
            "deepseek-flash": ModelPrice(0.30, 1.20, note=source),
            "deepseek-chat": ModelPrice(0.30, 1.20, note=source),
            "deepseek-v4-pro": ModelPrice(1.32, 3.96, note=source),
            "deepseek-reasoner": ModelPrice(0.55, 2.19, note="ASSUMED"),
        },
        # Pessimistic rather than free, so an unlisted model does not silently
        # cost nothing and slip past the ceiling.
        default=ModelPrice(2.00, 8.00, note="unknown model; deliberately pessimistic"),
    )


def scripted_handler(fixtures: Mapping[str, str] | None = None) -> Any:
    """Mock mode's model: fixtures for the shipped samples, `{}` for anything else.

    `fixtures` overrides it, which is what a test uses to script a specific reply.
    Without an override it answers from `mock_answers`, so `fdip run
    samples/invoice_digital.pdf` produces a real result with no provider and no
    spend -- the thing README_RUN.md tells a new reader to try first.
    """
    from fdip.adapters.mock_answers import answer_for

    def handler(messages: Sequence[Any]) -> str:
        return answer_for(messages, fixtures)

    return handler


def build_model_stack(
    settings: Settings,
    *,
    fixtures: Mapping[str, str] | None = None,
    handler: Any | None = None,
    ceiling_usd: float | None = None,
    already_spent_usd: float = 0.0,
    cache_path: str | None = None,
) -> ModelStack:
    from toolkit.cache import CachedLLM, SqliteCache
    from toolkit.governor import GovernedLLM, GovernorConfig

    mode = settings.provider_mode
    remaining = max(0.0, (ceiling_usd if ceiling_usd is not None
                          else settings.monthly_ceiling_usd) - already_spent_usd)

    client: Any
    provider_name = mode
    if mode == "mock":
        from toolkit.adapters import ScriptedLLM

        client = ScriptedLLM(
            handler=handler or scripted_handler(fixtures),
            model="mock-" + settings.model,
        )
        provider_name = "mock"
    else:
        from toolkit.llm_http import HttpLLM
        from toolkit.provider import resolve

        provider = resolve()
        client = HttpLLM(provider, prices=_deepseek_prices())
        provider_name = getattr(provider, "name", "deepseek")

    cache = SqliteCache(cache_path or str(settings.llm_cache_path))
    cached: Any = CachedLLM(client, cache)
    if mode == "recorded":
        cached = _ReplayOnly(cached)

    governed: Any = GovernedLLM(
        cached,
        GovernorConfig(
            max_cost_usd=remaining if mode == "live" else None,
            require_priced_calls=mode == "live",
            max_requests_per_minute=None,
        ),
    )
    switched = ThinkingSwitch(governed, client, settings.extract_thinking)
    return ModelStack(
        llm=switched, cache=cache, client=client, mode=mode,
        provider_name=provider_name, model=settings.model,
    )


class _ReplayOnly:
    """Recorded mode: a cache miss is an error, not a request.

    The point is that a test or a replay run cannot start spending because a
    prompt changed by one character. It fails loudly instead.
    """

    def __init__(self, cached: Any) -> None:
        self._cached = cached

    @property
    def model_version(self) -> str:
        return str(getattr(self._cached, "model_version", "cached"))

    def complete(self, messages: Sequence[Any], temperature: float = 0.0,
                 max_tokens: int | None = None) -> Any:
        before = self._calls()
        result = self._cached.complete(messages, temperature, max_tokens)
        usage = getattr(result, "usage", None)
        if usage is not None and not getattr(usage, "cached", False):
            raise ProviderUnavailable(
                "FDIP_PROVIDER_MODE=recorded and this prompt is not in the cache;"
                " the call was not sent (%d prior calls)" % before
            )
        return result

    def _calls(self) -> int:
        stats = getattr(self._cached, "stats", None)
        return int(getattr(stats, "misses", 0) or 0)


__all__ = [
    "ModelStack",
    "PLAIN_BODY",
    "ProviderUnavailable",
    "ThinkingSwitch",
    "build_model_stack",
    "scripted_handler",
]
