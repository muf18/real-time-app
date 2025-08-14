import asyncio
import logging
from typing import Dict, List, Type

from src.app_core.config import config
from src.app_core.networking.adapters.base import ExchangeAdapter
from src.app_core.networking.adapters.binance import BinanceAdapter
from src.app_core.networking.adapters.bitget import BitgetAdapter
from src.app_core.networking.adapters.bitstamp import BitstampAdapter
from src.app_core.networking.adapters.bitvavo import BitvavoAdapter
from src.app_core.networking.adapters.coinbase import CoinbaseAdapter
from src.app_core.networking.adapters.kraken import KrakenAdapter
from src.app_core.networking.adapters.okx import OKXAdapter
from src.app_core.services.publisher import raw_trade_publisher

ADAPTER_MAP: Dict[str, Type[ExchangeAdapter]] = {
    "Binance": BinanceAdapter,
    "Bitget": BitgetAdapter,
    "Bitstamp": BitstampAdapter,
    "Bitvavo": BitvavoAdapter,
    "Coinbase Exchange": CoinbaseAdapter,
    "Kraken": KrakenAdapter,
    "OKX": OKXAdapter,
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
        adapters = [
            ADAPTER_MAP[name](symbol) for name in exchange_names if name in ADAPTER_MAP
        ]

        for adapter in adapters:
            task = asyncio.create_task(self._run_adapter(adapter))
            self._tasks.append(task)
        logging.info(
            "ConnectionManager: Started %d adapters for %s", len(self._tasks), symbol
        )

    async def stop_all_connections(self):
        """Stops all active adapter tasks."""
        if not self._tasks:
            return

        logging.info("ConnectionManager: Stopping %d connections...", len(self._tasks))
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._current_symbol = None
        logging.info("ConnectionManager: All connections stopped.")

    async def _run_adapter(self, adapter: ExchangeAdapter):
        """A wrapper task to run an adapter's connection and publish its data."""
        logging.info("Starting connection for %s on %s", adapter.name, adapter.symbol)
        try:
            async for trade in adapter.connect_and_subscribe():
                await raw_trade_publisher.publish(trade)
        except asyncio.CancelledError:
            pass  # Expected on shutdown
        except Exception:
            logging.exception("Error in %s adapter", adapter.name)
        finally:
            logging.info(
                "Connection for %s on %s closed.", adapter.name, adapter.symbol
            )

```---

### Corrected `__init__.py` Files

The linter detected that many `__init__.py` files were missing a final newline. This has been corrected for all of them. The content is simple and serves to define the directories as Python packages.

**Location**: `src/app_core/__init__.py`
```python
# This file makes 'app_core' a Python package.