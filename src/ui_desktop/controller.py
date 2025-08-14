import asyncio
import logging
import queue
import threading
from typing import List

from PySide6.QtCore import QObject, QThread, Signal

from src.app_core.analytics.aggregator import SymbolAggregator
from src.app_core.config import config
from src.app_core.networking.manager import ADAPTER_MAP, ConnectionManager
from src.app_core.services.publisher import aggregated_data_publisher
from src.app_core.state_manager import state_manager
from src.schemas.market_data_pb2 import AggregatedDataPoint, Candle


class AsyncWorker(QObject):
    """
    Runs the asyncio event loop in a separate thread to avoid blocking the GUI.
    """

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.connection_manager = ConnectionManager()
        self.symbol_aggregator: SymbolAggregator | None = None

    def run(self):
        """The main entry point for the thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def switch_symbol_async(self, symbol: str):
        """Coroutine to switch the symbol being tracked."""
        if self.symbol_aggregator:
            await self.symbol_aggregator.stop()

        self.symbol_aggregator = SymbolAggregator(symbol, config.supported_timeframes)
        await self.symbol_aggregator.start()
        await self.connection_manager.switch_symbol(symbol)

    async def stop_all_async(self):
        """Coroutine to gracefully shut down all async tasks."""
        if self.symbol_aggregator:
            await self.symbol_aggregator.stop()
        await self.connection_manager.stop_all_connections()
        self.loop.stop()


class UIController(QObject):
    """
    The main controller that acts as a bridge between the async core and the Qt UI.
    """

    # Signals to emit data to the main UI thread
    new_aggregated_data = Signal(AggregatedDataPoint)
    historical_data_loaded = Signal(list)

    def __init__(self):
        super().__init__()
        self._async_worker = AsyncWorker()
        self._thread = QThread()
        self._async_worker.moveToThread(self._thread)

        self._thread.started.connect(self._async_worker.run)
        self._thread.start()

        self._ui_queue = aggregated_data_publisher.subscribe()
        self._start_listening()

    def _start_listening(self):
        """Starts a background task to listen for new data from the publisher."""
        listener_thread = threading.Thread(target=self._queue_listener, daemon=True)
        listener_thread.start()

    def _queue_listener(self):
        """
        Runs in a separate thread, pulling data from the asyncio world
        and emitting it as a Qt signal to the main UI thread.
        """
        while True:
            try:
                data_point: AggregatedDataPoint = self._ui_queue.get()
                self.new_aggregated_data.emit(data_point)
            except queue.Empty:
                continue

    def switch_symbol(self, symbol: str):
        """Public method called from the UI to change the active symbol."""
        logging.info("UIController: Switching to symbol %s", symbol)
        state_manager.update_symbol(symbol)
        asyncio.run_coroutine_threadsafe(
            self._async_worker.switch_symbol_async(symbol), self._async_worker.loop
        )

    def load_historical_data(self, symbol: str, timeframe: str):
        """Kicks off an async task to load historical data without blocking UI."""
        asyncio.run_coroutine_threadsafe(
            self._fetch_historical_data_async(symbol, timeframe),
            self._async_worker.loop,
        )

    async def _fetch_historical_data_async(self, symbol: str, timeframe: str):
        """The actual async method to fetch data."""
        exchange_name = config.exchange_integrations[symbol][0]
        adapter_class = ADAPTER_MAP.get(exchange_name)
        if adapter_class:
            adapter = adapter_class(symbol)
            candles: List[Candle] = await adapter.fetch_historical_data(timeframe, 500)
            self.historical_data_loaded.emit(candles)

    def shutdown(self):
        """Gracefully shuts down the async worker and the thread."""
        logging.info("UIController: Shutting down...")
        future = asyncio.run_coroutine_threadsafe(
            self._async_worker.stop_all_async(), self._async_worker.loop
        )
        try:
            future.result(timeout=5)  # Wait for shutdown to complete
        except TimeoutError:
            logging.error("Async worker shutdown timed out.")
        self._thread.quit()
        self._thread.wait()
        logging.info("UIController: Shutdown complete.")