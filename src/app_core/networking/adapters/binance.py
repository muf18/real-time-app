from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

import httpx
import orjson
import websockets
from backoff import expo, on_exception

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import Candle, PriceUpdate


class BinanceAdapter(ExchangeAdapter):
    """Adapter for Binance."""

    WSS_URL_BASE = "wss://stream.binance.com:9443/ws"
    REST_URL = "https://api.binance.com/api/v3"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.replace("/", "").lower()

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        """Connects to Binance WebSocket and streams trades."""
        url = f"{self.WSS_URL_BASE}/{self.exchange_symbol}@trade"
        async with websockets.connect(url) as websocket:
            while True:
                message_raw = await websocket.recv()
                message = orjson.loads(message_raw)
                if message.get("e") == "trade":
                    yield self._normalize_trade(message)

    def _normalize_trade(self, trade: Dict[str, Any]) -> PriceUpdate:
        """Converts a Binance JSON trade message to our Protobuf format."""
        client_received_ts = datetime.now(timezone.utc).isoformat()
        exchange_ts = datetime.fromtimestamp(
            trade["T"] / 1000, tz=timezone.utc
        ).isoformat()
        side = "SELL" if trade["m"] else "BUY"
        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=trade["p"],
            size=trade["q"],
            side=side,
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts,
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        """Fetches historical OHLCV data from Binance REST API."""
        url = f"{self.REST_URL}/klines"
        params = {
            "symbol": self.exchange_symbol.upper(),
            "interval": timeframe,
            "limit": limit,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            candles = []
            for row in data:
                candles.append(
                    Candle(
                        symbol=self.symbol,
                        timeframe=timeframe,
                        open_time_utc=datetime.fromtimestamp(
                            row[0] / 1000, tz=timezone.utc
                        ).isoformat(),
                        open=str(row[1]),
                        high=str(row[2]),
                        low=str(row[3]),
                        close=str(row[4]),
                        volume=str(row[5]),
                    )
                )
            return candles