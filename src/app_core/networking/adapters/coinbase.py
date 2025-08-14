import asyncio
import orjson
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any
import websockets
import httpx
from backoff import on_exception, expo

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import PriceUpdate, Candle
from src.app_core.services.publisher import raw_trade_publisher

class CoinbaseAdapter(ExchangeAdapter):
    """Adapter for Coinbase Exchange (formerly GDAX/Coinbase Pro)."""
    WSS_URL = "wss://ws-feed.exchange.coinbase.com"
    REST_URL = "https://api.exchange.coinbase.com"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.replace('/', '-')

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        """Connects to Coinbase WebSocket and streams trades."""
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": [self.exchange_symbol],
                "channels": ["matches"]
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                message = orjson.loads(message_raw)
                
                if message.get("type") == "match":
                    # This is a trade message, normalize and yield it
                    yield self._normalize_trade(message)

    def _normalize_trade(self, trade: Dict[str, Any]) -> PriceUpdate:
        """Converts a Coinbase JSON trade message to our Protobuf format."""
        client_received_ts = datetime.now(timezone.utc).isoformat()
        
        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=trade['price'],
            size=trade['size'],
            side=trade['side'].upper(),
            exchange_timestamp_utc=trade['time'],
            client_received_timestamp_utc=client_received_ts
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        """Fetches historical OHLCV data from Coinbase REST API."""
        # Coinbase API uses seconds for granularity
        granularity_map = {
            "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400
        }
        granularity = granularity_map.get(timeframe)
        if not granularity:
            # Handle unsupported timeframe for this exchange
            return []

        url = f"{self.REST_URL}/products/{self.exchange_symbol}/candles"
        params = {"granularity": granularity}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            candles = []
            # Data format: [time, low, high, open, close, volume]
            for row in reversed(data[:limit]):
                candles.append(Candle(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    open_time_utc=datetime.fromtimestamp(row[0], tz=timezone.utc).isoformat(),
                    open=str(row[3]),
                    high=str(row[2]),
                    low=str(row[1]),
                    close=str(row[4]),
                    volume=str(row[5])
                ))
            return candles