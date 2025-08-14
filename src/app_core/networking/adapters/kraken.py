import asyncio
import orjson
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any
import websockets
import httpx
from backoff import on_exception, expo

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import PriceUpdate, Candle

class KrakenAdapter(ExchangeAdapter):
    """Adapter for Kraken."""
    WSS_URL = "wss://ws.kraken.com"
    REST_URL = "https://api.kraken.com/0/public"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.upper()

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        """Connects to Kraken WebSocket and streams trades."""
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "event": "subscribe",
                "pair": [self.exchange_symbol],
                "subscription": {"name": "trade"}
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                message = orjson.loads(message_raw)
                
                if isinstance(message, list) and message[2] == "trade":
                    # Kraken sends trade data in a list format
                    for trade in message[1]:
                        yield self._normalize_trade(trade)

    def _normalize_trade(self, trade: List[Any]) -> PriceUpdate:
        """Converts a Kraken JSON trade message to our Protobuf format."""
        # trade format: [<price>, <volume>, <time>, <side>, <order_type>, <misc>]
        client_received_ts = datetime.now(timezone.utc).isoformat()
        exchange_ts = datetime.fromtimestamp(float(trade[2]), tz=timezone.utc).isoformat()
        
        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=str(trade[0]),
            size=str(trade[1]),
            side="BUY" if trade[3] == 'b' else "SELL",
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        """Fetches historical OHLCV data from Kraken REST API."""
        interval_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080
        }
        interval = interval_map.get(timeframe)
        if not interval:
            return []

        url = f"{self.REST_URL}/OHLC"
        params = {"pair": self.exchange_symbol, "interval": interval}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            # The actual data is nested under the pair name
            data = response.json()['result'][self.exchange_symbol]
            
            candles = []
            # Data format: [time, open, high, low, close, vwap, volume, count]
            for row in data[-limit:]:
                candles.append(Candle(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    open_time_utc=datetime.fromtimestamp(row[0], tz=timezone.utc).isoformat(),
                    open=str(row[1]),
                    high=str(row[2]),
                    low=str(row[3]),
                    close=str(row[4]),
                    volume=str(row[6])
                ))
            return candles