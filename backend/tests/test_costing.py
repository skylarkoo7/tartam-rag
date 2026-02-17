from app.pricing import PricingCatalog, UsageCollector, build_cost_summary, usage_cost_usd, UsageEvent


def test_usage_cost_formula_with_cached_tokens() -> None:
    event = UsageEvent(
        stage="generate_answer",
        provider="openai",
        model="gpt-5.2",
        endpoint="responses",
        input_tokens=1000,
        cached_input_tokens=400,
        output_tokens=500,
    )
    rates = {
        "input_per_1m_usd": 5.0,
        "cached_input_per_1m_usd": 0.5,
        "output_per_1m_usd": 15.0,
    }
    usd = usage_cost_usd(event, rates)
    expected = (600 / 1_000_000.0) * 5.0 + (400 / 1_000_000.0) * 0.5 + (500 / 1_000_000.0) * 15.0
    assert abs(usd - expected) < 1e-12


def test_build_cost_summary_aggregates_inr_and_usd() -> None:
    collector = UsageCollector()
    collector.add(
        stage="plan_query",
        provider="openai",
        model="gpt-5.2",
        endpoint="responses",
        input_tokens=2000,
        cached_input_tokens=0,
        output_tokens=200,
    )
    collector.add(
        stage="query_embedding",
        provider="openai",
        model="text-embedding-3-large",
        endpoint="embeddings",
        input_tokens=1000,
    )

    catalog = PricingCatalog(
        version="test-v1",
        source_url="https://example.com",
        rows=[
            {
                "model": "gpt-5.2",
                "endpoint": "responses",
                "input_per_1m_usd": 5.0,
                "cached_input_per_1m_usd": 0.5,
                "output_per_1m_usd": 15.0,
            },
            {
                "model": "text-embedding-3-large",
                "endpoint": "embeddings",
                "input_per_1m_usd": 0.13,
            },
        ],
    )

    summary = build_cost_summary(
        collector=collector,
        catalog=catalog,
        fx_rate=84.0,
        fx_source="cache:fresh",
    )
    assert summary.total_usd > 0
    assert summary.total_inr > 0
    assert len(summary.line_items) == 2
    assert summary.fx_source == "cache:fresh"
