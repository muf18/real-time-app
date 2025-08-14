import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.app_core.analytics.aggregator import SymbolAggregator, TimeFrameAggregator
from src.app_core.services.publisher import (
    aggregated_data_publisher,
    raw_trade_publisher,
)
from src.schemas.market_data_pb2 import AggregatedDataPoint, PriceUpdate

# Use pytest-asyncio for async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_trades():
    """Provides a list of sample PriceUpdate objects for testing."""
    now = datetime.now(timezone.utc)
    return [
        PriceUpdate(
            symbol="BTC/USD", exchange="Test", price="50000", size="1",
            side="BUY", exchange_timestamp_utc=now.isoformat()
        ),
        PriceUpdate(
            symbol="BTC/USD", exchange="Test", price="50010", size="2",
            side="SELL",
            exchange_timestamp_utc=(now + timedelta(seconds=10)).isoformat(),
        ),
        PriceUpdate(
            symbol="BTC/USD", exchange="Test", price="50005", size="1.5",
            side="BUY",
            exchange_timestamp_utc=(now + timedelta(seconds=20)).isoformat(),
        ),
    ]


class TestTimeFrameAggregator:
    async def test_vwap_calculation(self, sample_trades):
        """Validates that the VWAP calculation is correct."""
        aggregator = TimeFrameAggregator(symbol="BTC/USD", timeframe="1m")

        # (50000 * 1) + (50010 * 2) + (50005 * 1.5) = 225027.5
        # Total Volume = 1 + 2 + 1.5 = 4.5
        # Expected VWAP = 225027.5 / 4.5 = 50006.11111111
        expected_vwap = Decimal("50006.11111111")

        for trade in sample_trades:
            await aggregator.add_trade(trade)

        trade_data = aggregator.trades
        prices = [d[0] for d in trade_data]
        sizes = [d[1] for d in trade_data]

        total_volume = sum(sizes)
        vwap = sum(p * s for p, s in zip(prices, sizes)) / total_volume

        assert total_volume == Decimal("4.5")
        assert pytest.approx(vwap, rel=1e-9) == expected_vwap
        assert aggregator.last_price == Decimal("50005")
        assert aggregator.high_price == Decimal("50010")
        assert aggregator.low_price == Decimal("50000")

    async def test_candle_finalization_and_publish(self):
        """Ensures a new candle is created and the old one is published."""
        now = datetime.now(timezone.utc).replace(second=30, microsecond=0)
        aggregator = TimeFrameAggregator(symbol="BTC/USD", timeframe="1m")
        subscriber_queue = aggregated_data_publisher.subscribe()

        trade1 = PriceUpdate(
            symbol="BTC/USD", exchange="Test", price="100", size="1",
            side="BUY", exchange_timestamp_utc=now.isoformat()
        )
        await aggregator.add_trade(trade1)

        trade2 = PriceUpdate(
            symbol="BTC/USD", exchange="Test", price="200", size="2",
            side="BUY",
            exchange_timestamp_utc=(now + timedelta(minutes=1)).isoformat(),
        )
        await aggregator.add_trade(trade2)

        try:
            published: AggregatedDataPoint = await asyncio.wait_for(
                subscriber_queue.get(), timeout=1
            )
            assert published.symbol == "BTC/USD"
            assert published.timeframe == "1m"
            assert Decimal(published.last_price) == Decimal("100")
            assert Decimal(published.vwap) == Decimal("100")
            assert Decimal(published.cumulative_volume) == Decimal("1")
        except asyncio.TimeoutError:
            pytest.fail("Aggregator did not publish the finalized candle.")

        assert aggregator.last_price == Decimal("200")
        assert len(aggregator.trades) == 1


class TestSymbolAggregator:
    async def test_trade_distribution(self, sample_trades):
        """Tests that the SymbolAggregator correctly distributes trades."""
        class MockTimeFrameAggregator:
            def __init__(self, symbol, timeframe):
                self.received_trades = []
            async def add_trade(self, trade):
                self.received_trades.append(trade)

        aggregator = SymbolAggregator("BTC/USD", ["1m", "5m"])

        mock_1m = MockTimeFrameAggregator("BTC/USD", "1m")
        mock_5m = MockTimeFrameAggregator("BTC/USD", "5m")
        aggregator._timeframe_aggregators = {"1m": mock_1m, "5m": mock_5m}
        await aggregator.start()

        for trade in sample_trades:
            await raw_trade_publisher.publish(trade)
        await asyncio.sleep(0.01)

        eth_trade = PriceUpdate(
            symbol="ETH/USD", exchange="Test", price="4000", size="10",
            side="BUY", exchange_timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        await raw_trade_publisher.publish(eth_trade)
        await asyncio.sleep(0.01)
        await aggregator.stop()

        assert len(mock_1m.received_trades) == 3
        assert len(mock_5m.received_trades) == 3
        assert mock_1m.received_trades[0].price == "50000"