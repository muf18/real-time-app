from abc import ABC, abstractmethod
from typing import AsyncGenerator, List
from src.schemas.market_data_pb2 import PriceUpdate, Candle

class ExchangeAdapter(ABC):
    """Abstract Base Class for all exchange integrations."""
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.name = self.__class__.__name__.replace("Adapter", "")

    @abstractmethod
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        """
        Connects to the WebSocket, subscribes to trades, and yields
        normalized PriceUpdate messages. This method should handle
        reconnections internally.
        """
        yield

    @abstractmethod
    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        """
        Fetches historical candlestick data from the exchange's REST API.
        """
        pass

    def _normalize_symbol(self, exchange_symbol: str) -> str:
        """A default helper to normalize symbols, can be overridden."""
        return exchange_symbol.replace('-', '/').upper()