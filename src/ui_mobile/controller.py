import asyncio
import logging
import queue
import threading
from typing import Callable, List

from kivy.clock import Clock

from src.app_core.analytics.aggregator import SymbolAggregator
from src.app_core.config import config
from src.app_core.networking.manager import ADAPTER_MAP, ConnectionManager
from src.app_core.services.publisher import aggregated_data_publisher
from src.app_core.state_manager import state_manager
from src.schemas.market_data_pb2 import AggregatedDataPoint, Candle


class KivyController:
    """
    Manages the asyncio event loop and bridges it to the Kivy UI thread.
    """

    def __init__(self):
        self._async_loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._connection_manager = ConnectionManager()
        self._symbol_aggregator: SymbolAggregator | None = None
        self._ui_update_queue = queue.Queue()
        self._data_subscriber_queue = aggregated_data_publisher.subscribe()
        self.on_new_data: Callable[[AggregatedDataPoint], None] | None = None
        self.on_historical_data: Callable[[List[Candle]], None] | None = None

    def start(self):
        """Starts the background asyncio thread and the Kivy polling clock."""
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._listen_for_data(), self._async_loop)
        Clock.schedule_interval(self._poll_queue, 1.0 / 60.0)

    def _run_async_loop(self):
        """The main entry point for the background thread."""
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def _poll_queue(self, _dt):
        """Called by Kivy's clock to check for new data and update the UI."""
        while not self._ui_update_queue.empty():
            event_type, data = self._ui_update_queue.get()
            if event_type == "new_data" and self.on_new_data:
                self.on_new_data(data)
            elif event_type == "historical_data" and self.on_historical_data:
                self.on_historical_data(data)

    async def _listen_for_data(self):
        """Listens on the publisher queue and puts data into the thread-safe queue."""
        while True:
            data_point: AggregatedDataPoint = await self._data_subscriber_queue.get()
            self._ui_update_queue.put(("new_data", data_point))

    def switch_symbol(self, symbol: str):
        """Public method to change the active symbol."""
        state_manager.update_symbol(symbol)
        asyncio.run_coroutine_threadsafe(
            self._switch_symbol_async(symbol), self._async_loop
        )

    async def _switch_symbol_async(self, symbol: str):
        if self._symbol_aggregator:
            await self._symbol_aggregator.stop()

        self._symbol_aggregator = SymbolAggregator(symbol, config.supported_timeframes)
        await self._symbol_aggregator.start()
        await self._connection_manager.switch_symbol(symbol)

    def load_historical_data(self, symbol: str, timeframe: str):
        """Kicks off an async task to load historical data."""
        asyncio.run_coroutine_threadsafe(
            self._fetch_historical_data_async(symbol, timeframe), self._async_loop
        )

    async def _fetch_historical_data_async(self, symbol: str, timeframe: str):
        exchange_name = config.exchange_integrations[symbol][0]
        adapter_class = ADAPTER_MAP.get(exchange_name)
        if adapter_class:
            adapter = adapter_class(symbol)
            candles = await adapter.fetch_historical_data(timeframe, 100)
            self._ui_update_queue.put(("historical_data", candles))

    def shutdown(self):
        """Gracefully shuts down the async worker."""
        if self._async_loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._async_loop)

    async def _shutdown_async(self):
        if self._symbol_aggregator:
            await self._symbol_aggregator.stop()
        await self._connection_manager.stop_all_connections()
        self._async_loop.stop()