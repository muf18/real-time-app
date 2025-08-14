import asyncio
import orjson
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any
import websockets
import httpx
from backoff import on_exception, expo

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import PriceUpdate, Candle

class BitstampAdapter(ExchangeAdapter):
    """Adapter for Bitstamp."""
    WSS_URL = "wss://ws.bitstamp.net"
    REST_URL = "https://www.bitstamp.net/api/v2"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        # Bitstamp uses lowercase symbols without slashes for channels
        self.exchange_symbol = symbol.replace('/', '').lower()

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        """Connects to Bitstamp WebSocket and streams live trades."""
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "event": "bts:subscribe",
                "data": {
                    "channel": f"live_trades_{self.exchange_symbol}"
                }
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                message = orjson.loads(message_raw)
                
                if message.get("event") == "trade":
                    yield self._normalize_trade(message['data'])

    def _normalize_trade(self, trade: Dict[str, Any]) -> PriceUpdate:
        """Converts a Bitstamp JSON trade message to our Protobuf format."""
        client_received_ts = datetime.now(timezone.utc).isoformat()
        # Bitstamp timestamp is a unix timestamp string
        exchange_ts = datetime.fromtimestamp(int(trade['timestamp']), tz=timezone.utc).isoformat()
        
        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=str(trade['price']),
            size=str(trade['amount']),
            # 0 for buy, 1 for sell
            side="BUY" if trade['type'] == 0 else "SELL",
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        """Fetches historical OHLCV data from Bitstamp REST API."""
        step_map = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400
        }
        step = step_map.get(timeframe)
        if not step:
            return []

        url = f"{self.REST_URL}/ohlc/{self.exchange_symbol}/"
        params = {"step": step, "limit": limit}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()['data']['ohlc']
            
            candles = []
            # Data format: list of dicts with 'timestamp', 'open', 'high', 'low', 'close', 'volume'
            for row in data:
                candles.append(Candle(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    open_time_utc=datetime.fromtimestamp(int(row['timestamp']), tz=timezone.utc).isoformat(),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                ))
            return candles