from datetime import datetime, timezone
from typing import AsyncGenerator, List

import httpx
import orjson
import websockets
from backoff import expo, on_exception

from src.app_core.networking.adapters.base import ExchangeAdapter
from src.schemas.market_data_pb2 import Candle, PriceUpdate


class BitgetAdapter(ExchangeAdapter):
    """Adapter for Bitget."""

    WSS_URL = "wss://ws.bitget.com/v2/spot/public"
    REST_URL = "https://api.bitget.com/api/v2/spot/market"

    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.exchange_symbol = symbol.replace("/", "")

    @on_exception(expo, (websockets.ConnectionClosedError, ConnectionRefusedError), max_tries=8)
    async def connect_and_subscribe(self) -> AsyncGenerator[PriceUpdate, None]:
        async with websockets.connect(self.WSS_URL) as websocket:
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "instType": "SPOT",
                        "channel": "trade",
                        "instId": self.exchange_symbol,
                    }
                ],
            }
            await websocket.send(orjson.dumps(subscribe_msg))

            while True:
                message_raw = await websocket.recv()
                if "ping" in str(message_raw):
                    await websocket.send('{"pong"}')
                    continue

                message = orjson.loads(message_raw)
                if (message.get("action") == "snapshot" and
                        message.get("arg", {}).get("channel") == "trade"):
                    for trade in message["data"]:
                        yield self._normalize_trade(trade)

    def _normalize_trade(self, trade: List[str]) -> PriceUpdate:
        # trade format: [timestamp, price, size, side]
        client_received_ts = datetime.now(timezone.utc).isoformat()
        exchange_ts = datetime.fromtimestamp(
            int(trade[0]) / 1000, tz=timezone.utc
        ).isoformat()

        return PriceUpdate(
            symbol=self.symbol,
            exchange=self.name,
            price=trade[1],
            size=trade[2],
            side=trade[3].upper(),  # "buy" or "sell"
            exchange_timestamp_utc=exchange_ts,
            client_received_timestamp_utc=client_received_ts,
        )

    async def fetch_historical_data(self, timeframe: str, limit: int) -> List[Candle]:
        granularity_map = {
            "1m": "60", "5m": "300", "15m": "900",
            "1h": "3600", "4h": "14400", "1d": "86400",
        }
        granularity = granularity_map.get(timeframe)
        if not granularity:
            return []

        url = f"{self.REST_URL}/candles"
        params = {
            "symbol": self.exchange_symbol,
            "granularity": granularity,
            "limit": limit,
        }

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