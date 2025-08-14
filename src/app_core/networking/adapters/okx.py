from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

import httpx
import orjson
import websockets
from backoff import expo, on_exception

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import Candle, PriceUpdate


class OKXAdapter(ExchangeAdapter):
    """Adapter for OKX."""

    WSS_URL = "wss://ws.okx.com:8443/ws/v5/public"
    REST_URL = "https://www.okx.com/api/v5/market"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.replace("/", "-")

    @on_exception(
        expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8
    )
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": "trades", "instId": self.exchange_symbol}],
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                if message_raw == b"ping":
                    await websocket.send(b"pong")
                    continue

                message = orjson.loads(message_raw)
                if message.get("arg", {}).get("channel") == "trades":
                    for trade in message["data"]:
                        yield self._normalize_trade(trade)

    def _normalize_trade(self, trade: Dict[str, Any]) -> PriceUpdate:
        client_received_ts = datetime.now(timezone.utc).isoformat()
        exchange_ts = datetime.fromtimestamp(
            int(trade["ts"]) / 1000, tz=timezone.utc
        ).isoformat()

        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=trade["px"],
            size=trade["sz"],
            side=trade["side"].upper(),
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts,
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        bar_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W",
        }
        bar = bar_map.get(timeframe)
        if not bar:
            return []

        url = f"{self.REST_URL}/candles"
        params = {"instId": self.exchange_symbol, "bar": bar, "limit": limit}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()["data"]

            candles = []
            for row in data:
                candles.append(
                    Candle(
                        symbol=self.symbol,
                        timeframe=timeframe,
                        open_time_utc=datetime.fromtimestamp(
                            int(row[0]) / 1000, tz=timezone.utc
                        ).isoformat(),
                        open=str(row[1]),
                        high=str(row[2]),
                        low=str(row[3]),
                        close=str(row[4]),
                        volume=str(row[5]),
                    )
                )
            return candles