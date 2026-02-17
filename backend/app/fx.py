from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from .db import Database


@dataclass(slots=True)
class FxQuote:
    rate: float
    source: str
    as_of: str


class FxService:
    def __init__(
        self,
        *,
        db: Database,
        primary_url: str,
        refresh_hours: int,
        fallback_rate: float,
    ):
        self.db = db
        self.primary_url = primary_url
        self.refresh_hours = max(1, int(refresh_hours or 6))
        self.fallback_rate = float(fallback_rate or 0.0)

    def get_usd_inr(self) -> FxQuote:
        latest = self.db.get_latest_fx_rate()
        if latest and self._is_fresh(latest.get("fetched_at")):
            return FxQuote(
                rate=float(latest["usd_inr"]),
                source="cache:fresh",
                as_of=str(latest.get("fetched_at", "")),
            )

        fetched = self._fetch_live_rate()
        if fetched is not None:
            rate, as_of = fetched
            self.db.record_fx_rate(source="frankfurter", usd_inr=rate, fetched_at=as_of)
            return FxQuote(rate=rate, source="live:frankfurter", as_of=as_of)

        if latest:
            return FxQuote(
                rate=float(latest["usd_inr"]),
                source="cache:stale",
                as_of=str(latest.get("fetched_at", "")),
            )

        now = datetime.now(UTC).isoformat()
        rate = self.fallback_rate if self.fallback_rate > 0 else 83.0
        return FxQuote(rate=rate, source="fallback", as_of=now)

    def _fetch_live_rate(self) -> tuple[float, str] | None:
        try:
            with httpx.Client(timeout=12.0) as client:
                response = client.get(self.primary_url)
                response.raise_for_status()
                payload = response.json()
            rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
            value = float(rates.get("INR"))
            if value <= 0:
                return None
            as_of = str(payload.get("date") or datetime.now(UTC).date().isoformat())
            return value, as_of
        except Exception:
            return None

    def _is_fresh(self, fetched_at: object) -> bool:
        if not fetched_at:
            return False
        try:
            text = str(fetched_at).strip()
            if "T" in text:
                when = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                when = datetime.fromisoformat(f"{text}T00:00:00+00:00")
            return datetime.now(UTC) - when.astimezone(UTC) <= timedelta(hours=self.refresh_hours)
        except Exception:
            return False
