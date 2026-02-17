from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import Database
from app.fx import FxService


def test_fx_service_uses_fresh_cache_before_network(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init_db()
    now = datetime.now(UTC).isoformat()
    db.record_fx_rate(source="manual", usd_inr=84.5, fetched_at=now)

    fx = FxService(
        db=db,
        primary_url="http://127.0.0.1:9/unreachable",
        refresh_hours=6,
        fallback_rate=82.0,
    )
    quote = fx.get_usd_inr()
    assert quote.source == "cache:fresh"
    assert abs(quote.rate - 84.5) < 1e-9


def test_fx_service_falls_back_to_stale_cache_when_live_fails(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init_db()
    stale = (datetime.now(UTC) - timedelta(days=3)).date().isoformat()
    db.record_fx_rate(source="manual", usd_inr=85.2, fetched_at=stale)

    fx = FxService(
        db=db,
        primary_url="http://127.0.0.1:9/unreachable",
        refresh_hours=1,
        fallback_rate=82.0,
    )
    quote = fx.get_usd_inr()
    assert quote.source == "cache:stale"
    assert abs(quote.rate - 85.2) < 1e-9
