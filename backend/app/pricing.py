from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import CostSummary, UsageLineItem


@dataclass(slots=True)
class UsageEvent:
    stage: str
    provider: str
    model: str
    endpoint: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class UsageCollector:
    events: list[UsageEvent] = field(default_factory=list)

    def add(
        self,
        *,
        stage: str,
        provider: str,
        model: str,
        endpoint: str,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        self.events.append(
            UsageEvent(
                stage=stage,
                provider=provider,
                model=model,
                endpoint=endpoint,
                input_tokens=max(0, int(input_tokens or 0)),
                cached_input_tokens=max(0, int(cached_input_tokens or 0)),
                output_tokens=max(0, int(output_tokens or 0)),
            )
        )

    def extend(self, events: list[UsageEvent]) -> None:
        self.events.extend(events)


@dataclass(slots=True)
class PricingCatalog:
    version: str
    source_url: str
    rows: list[dict[str, Any]]

    @classmethod
    def load(cls, path: Path) -> "PricingCatalog":
        payload = json.loads(path.read_text(encoding="utf-8"))
        version = str(payload.get("version", "unknown"))
        source_url = str(payload.get("source_url", ""))
        rows = [dict(item) for item in payload.get("models", []) if isinstance(item, dict)]
        return cls(version=version, source_url=source_url, rows=rows)

    def lookup(self, model: str, endpoint: str) -> dict[str, float] | None:
        target_model = (model or "").strip().lower()
        target_endpoint = (endpoint or "").strip().lower()
        for row in self.rows:
            row_model = str(row.get("model", "")).strip().lower()
            row_endpoint = str(row.get("endpoint", "")).strip().lower()
            if row_model == target_model and row_endpoint == target_endpoint:
                return {
                    "input_per_1m_usd": float(row.get("input_per_1m_usd", 0.0) or 0.0),
                    "cached_input_per_1m_usd": float(row.get("cached_input_per_1m_usd", 0.0) or 0.0),
                    "output_per_1m_usd": float(row.get("output_per_1m_usd", 0.0) or 0.0),
                }
        return None


def _round_usd(value: float) -> float:
    return round(float(value), 6)


def _round_inr(value: float) -> float:
    return round(float(value), 4)


def usage_cost_usd(event: UsageEvent, rates: dict[str, float] | None) -> float:
    if rates is None:
        return 0.0

    input_rate = float(rates.get("input_per_1m_usd", 0.0) or 0.0)
    cached_input_rate = float(rates.get("cached_input_per_1m_usd", 0.0) or 0.0)
    output_rate = float(rates.get("output_per_1m_usd", 0.0) or 0.0)

    # Embeddings are input-only in this cost model.
    if event.endpoint == "embeddings":
        return (event.input_tokens / 1_000_000.0) * input_rate

    non_cached_input = max(event.input_tokens - event.cached_input_tokens, 0)
    usd = (
        (non_cached_input / 1_000_000.0) * input_rate
        + (event.cached_input_tokens / 1_000_000.0) * cached_input_rate
        + (event.output_tokens / 1_000_000.0) * output_rate
    )
    return usd


def build_cost_summary(
    *,
    collector: UsageCollector,
    catalog: PricingCatalog,
    fx_rate: float,
    fx_source: str,
) -> CostSummary:
    line_items: list[UsageLineItem] = []
    total_usd = 0.0
    total_inr = 0.0

    for event in collector.events:
        rates = catalog.lookup(event.model, event.endpoint)
        usd = usage_cost_usd(event, rates)
        inr = usd * fx_rate
        total_usd += usd
        total_inr += inr
        line_items.append(
            UsageLineItem(
                stage=event.stage,  # type: ignore[arg-type]
                provider=event.provider,
                model=event.model,
                endpoint=event.endpoint,
                input_tokens=event.input_tokens,
                cached_input_tokens=event.cached_input_tokens,
                output_tokens=event.output_tokens,
                usd_cost=_round_usd(usd),
                inr_cost=_round_inr(inr),
                pricing_version=catalog.version,
                fx_rate=fx_rate,
            )
        )

    return CostSummary(
        total_usd=_round_usd(total_usd),
        total_inr=_round_inr(total_inr),
        currency_local="INR",
        fx_rate=fx_rate,
        fx_source=fx_source,
        line_items=line_items,
    )
