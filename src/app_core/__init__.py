# This file makes 'app_core' a Python package.```

#### **`src/app_core/config.py`**
```python
from pydantic import BaseModel, Field
from typing import Dict, List, Literal

SupportedSymbols = Literal[
    "BTC/USD",
    "BTC/EUR",
    "BTC/USDT",
]

SupportedExchanges = Literal[
    "Coinbase Exchange",
    "Bitstamp",
    "Kraken",
    "Bitvavo",
    "Binance",
    "OKX",
    "Bitget",
]

class AppConfig(BaseModel):
    """Strongly-typed application configuration."""
    supported_timeframes: List[str] = Field(default_factory=lambda: [
        "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"
    ])
    
    exchange_integrations: Dict[SupportedSymbols, List[SupportedExchanges]] = Field(
        default_factory=lambda: {
            "BTC/USD": ["Coinbase Exchange", "Bitstamp", "Kraken"],
            "BTC/EUR": ["Kraken", "Bitvavo"],
            "BTC/USDT": ["Binance", "OKX", "Bitget"]
        }
    )
    
    # Latency budget in milliseconds
    latency_budget_ms: int = 300
    
    # Maximum number of historical candles to fetch
    historical_data_limit: int = 1000

# Global config instance
config = AppConfig()