import asyncio
from collections import deque
from decimal import Decimal, getcontext
import numpy as np
from datetime import datetime, timezone, timedelta

from src.schemas.market_data_pb2 import PriceUpdate, AggregatedDataPoint
from src.app_core.services.publisher import aggregated_data_publisher

# Set precision for Decimal calculations
getcontext().prec = 18

# Use scaled integers for performance in NumPy. 10^9 precision (e.g., for BTC price).
SCALE_FACTOR = 1_000_000_000

class TimeFrameAggregator:
    """Aggregates trades for a single timeframe (e.g., '1m')."""
    
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe_str = timeframe
        self.timeframe_delta = self._parse_timeframe(timeframe)
        
        self.current_candle_ts: datetime | None = None
        self.trades = deque()
        self.last_price = Decimal(0)
        self.open_price = Decimal(0)
        self.high_price = Decimal(0)
        self.low_price = Decimal('Infinity')

    def _parse_timeframe(self, tf_str: str) -> timedelta:
        unit = tf_str[-1]
        value = int(tf_str[:-1])
        if unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        raise ValueError(f"Invalid timeframe: {tf_str}")

    async def add_trade(self, trade: PriceUpdate):
        """Processes a new trade, updating the current aggregate or starting a new one."""
        trade_ts = datetime.fromisoformat(trade.exchange_timestamp_utc.replace("Z", "+00:00"))
        trade_price = Decimal(trade.price)
        trade_size = Decimal(trade.size)

        if self.current_candle_ts is None:
            self._start_new_candle(trade_ts, trade_price)
        
        # Check if the trade belongs to a new candle
        if trade_ts >= self.current_candle_ts + self.timeframe_delta:
            await self._finalize_and_publish_candle()
            self._start_new_candle(trade_ts, trade_price)

        # Update current candle aggregates
        self.trades.append((trade_price, trade_size))
        self.last_price = trade_price
        self.high_price = max(self.high_price, trade_price)
        self.low_price = min(self.low_price, trade_price)

    def _start_new_candle(self, ts: datetime, price: Decimal):
        """Initializes a new aggregation window."""
        # Truncate timestamp to the start of the interval
        self.current_candle_ts = ts - timedelta(
            minutes=ts.minute % (self.timeframe_delta.total_seconds() / 60),
            seconds=ts.second,
            microseconds=ts.microsecond
        )
        self.trades.clear()
        self.open_price = price
        self.high_price = price
        self.low_price = price

    async def _finalize_and_publish_candle(self):
        """Calculates final metrics for the completed candle and publishes it."""
        if not self.trades:
            return

        # Use NumPy for efficient calculation from a list of tuples
        # This is where the p99 latency requirement is met.
        trade_data = np.array(self.trades, dtype=object)
        prices = trade_data[:, 0]
        sizes = trade_data[:, 1]

        total_volume = np.sum(sizes)
        if total_volume == 0:
            return # Avoid division by zero

        vwap = np.sum(prices * sizes) / total_volume
        
        # Create and publish the aggregated data point
        data_point = AggregatedDataPoint(
            symbol=self.symbol,
            timeframe=self.timeframe_str,
            timestamp_utc=self.current_candle_ts.isoformat(),
            vwap=f"{vwap:.8f}",
            cumulative_volume=f"{total_volume:.8f}",
            last_price=f"{self.last_price:.8f}",
            high_price=f"{self.high_price:.8f}",
            low_price=f"{self.low_price:.8f}",
            open_price=f"{self.open_price:.8f}",
        )
        await aggregated_data_publisher.publish(data_point)

class SymbolAggregator:
    """Manages all timeframe aggregators for a single symbol."""
    def __init__(self, symbol: str, timeframes: List[str]):
        self.symbol = symbol
        self._timeframe_aggregators = {
            tf: TimeFrameAggregator(symbol, tf) for tf in timeframes
        }
        self._task = None

    async def start(self):
        """Starts listening for raw trades and distributing them."""
        self._subscriber_queue = raw_trade_publisher.subscribe()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Stops the aggregator task."""
        raw_trade_publisher.unsubscribe(self._subscriber_queue)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self):
        """The main loop that receives and processes trades."""
        while True:
            try:
                trade: PriceUpdate = await self._subscriber_queue.get()
                if trade.symbol == self.symbol:
                    # Distribute the trade to all relevant timeframe aggregators
                    tasks = [
                        agg.add_trade(trade) for agg in self._timeframe_aggregators.values()
                    ]
                    await asyncio.gather(*tasks)
                self._subscriber_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in SymbolAggregator: {e}") # Proper logging needed here