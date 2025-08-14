import asyncio
from typing import List, Dict, Type

from src.app_core.config import config
from src.app_core.networking.adapters.base import ExchangeAdapter
from src.app_core.networking.adapters.coinbase import CoinbaseAdapter
from src.app_core.networking.adapters.bitstamp import BitstampAdapter
from src.app_core.networking.adapters.kraken import KrakenAdapter
from src.app_core.networking.adapters.binance import BinanceAdapter
from src.app_core.networking.adapters.bitvavo import BitvavoAdapter
from src.app_core.networking.adapters.okx import OKXAdapter
from src.app_core.networking.adapters.bitget import BitgetAdapter
from src.app_core.services.publisher import raw_trade_publisher
from src.schemas.market_data_pb2 import PriceUpdate

ADAPTER_MAP: Dict[str, Type[ExchangeAdapter]] = {
    "Coinbase Exchange": CoinbaseAdapter,
    "Bitstamp": BitstampAdapter,
    "Kraken": KrakenAdapter,
    "Binance": BinanceAdapter,
    "Bitvavo": BitvavoAdapter,
    "OKX": OKXAdapter,
    "Bitget": BitgetAdapter
}

class ConnectionManager:
    """Manages the lifecycle of exchange adapter connections for a symbol."""
    def __init__(self):
        self._tasks: List[asyncio.Task] = []
        self._current_symbol: str | None = None

    async def switch_symbol(self, symbol: str):
        """Stops current connections and starts new ones for the given symbol."""
        if self._current_symbol == symbol:
            return
        
        await self.stop_all_connections()
        self._current_symbol = symbol
        
        exchange_names = config.exchange_integrations.get(symbol, [])
        adapters = [ADAPTER_MAP[name](symbol) for name in exchange_names if name in ADAPTER_MAP]
        
        for adapter in adapters:
            task = asyncio.create_task(self._run_adapter(adapter))
            self._tasks.append(task)
        print(f"ConnectionManager: Started {len(self._tasks)} adapters for {symbol}")

    async def stop_all_connections(self):
        """Stops all active adapter tasks."""
        if not self._tasks:
            return
        
        print(f"ConnectionManager: Stopping {len(self._tasks)} connections...")
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._current_symbol = None
        print("ConnectionManager: All connections stopped.")

    async def _run_adapter(self, adapter: ExchangeAdapter):
        """A wrapper task to run an adapter's connection and publish its data."""
        try:
            print(f"Starting connection for {adapter.name} on {adapter.symbol}")
            async for trade in adapter.connect_and_subscribe():
                await raw_trade_publisher.publish(trade)
        except asyncio.CancelledError:
            pass # Expected on shutdown
        except Exception as e:
            # Proper logging should be used here
            print(f"Error in {adapter.name} adapter: {e}")
        finally:
            print(f"Connection for {adapter.name} on {adapter.symbol} closed.")