import asyncio

from qrdesk_gateway import provider


def test_bundle_marks_last_price_as_completed_bar_close(monkeypatch):
    bars = [
        {"time": 1_700_000_000_000, "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000.0},
        {"time": 1_700_000_300_000, "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 1200.0},
    ]
    session = {
        "market": "US",
        "calendar": "XNYS",
        "sessionDate": "2023-11-14",
        "state": "post_close",
        "isTradingDay": True,
        "openTime": 1_699_970_000_000,
        "breakStart": None,
        "breakEnd": None,
        "closeTime": 1_700_000_600_000,
    }

    async def fake_massive(instrument, range_key):
        return bars, "delayed", [], {
            "duplicateCount": 0,
            "invalidCount": 0,
            "futureCount": 0,
            "offSessionCount": 0,
            "incompleteCount": 0,
            "truncatedSegmentCount": 0,
            "partialAggregationCount": 0,
        }, session

    monkeypatch.setattr(provider, "_massive", fake_massive)
    result = asyncio.run(provider.get_bundle("US.AAPL", "AAPL", "1d", "5m"))

    assert result["quote"]["lastPrice"] == 102.0
    assert result["quote"]["priceSemantics"] == "last-completed-bar-close"
    assert result["quote"]["isIndependentQuote"] is False
    assert result["provenance"]["quoteSemantics"] == "last-completed-bar-close"
    assert result["provenance"]["syntheticBars"] == 0
