import asyncio
import orjson
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any
import websockets
import httpx
from backoff import on_exception, expo

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import PriceUpdate, Candle

class BitvavoAdapter(ExchangeAdapter):
    """Adapter for Bitvavo."""
    WSS_URL = "wss://ws.bitvavo.com/v2/"
    REST_URL = "https://api.bitvavo.com/v2"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.replace('/', '-')

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "action": "subscribe",
                "channels": [{"name": "trades", "markets": [self.exchange_symbol]}]
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                message = orjson.loads(message_raw)
                
                if message.get("event") == "trade":
                    yield self._normalize_trade(message)

    def _normalize_trade(self, trade: Dict[str, Any]) -> PriceUpdate:
        client_received_ts = datetime.now(timezone.utc).isoformat()
        exchange_ts = datetime.fromtimestamp(trade['timestamp'] / 1000, tz=timezone.utc).isoformat()
        
        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=trade['price'],
            size=trade['amount'],
            side=trade['side'].upper(),
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        url = f"{self.REST_URL}/{self.exchange_symbol}/candles"
        params = {"interval": timeframe, "limit": limit}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            candles = []
            # Data format: [timestamp, open, high, low, close, volume]
            for row in data:
                candles.append(Candle(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    open_time_utc=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).isoformat(),
                    open=str(row[1]),
                    high=str(row[2]),
                    low=str(row[3]),
                    close=str(row[4]),
                    volume=str(row[5])
                ))
            return candles