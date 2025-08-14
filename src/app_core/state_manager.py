import logging
from pathlib import Path

import orjson
from pydantic import BaseModel, Field


class AppState(BaseModel):
    """Strongly-typed application persistent state."""
    last_symbol: str = Field(default="BTC/USD")
    last_timeframe: str = Field(default="1h")


class StateManager:
    """Handles loading and saving the application's persistent state."""

    def __init__(self, file_path: Path):
        self._file_path = file_path
        self._state = self._load_state()

    def _load_state(self) -> AppState:
        """Loads state from JSON file, or returns default if not found/invalid."""
        if not self._file_path.exists():
            return AppState()
        try:
            with self._file_path.open("rb") as f:
                data = orjson.loads(f.read())
                return AppState(**data)
        except (orjson.JSONDecodeError, TypeError, ValueError, OSError):
            # If file is corrupt or unreadable, start with a default state
            return AppState()

    def save_state(self):
        """Saves the current state to the JSON file."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_path.open("wb") as f:
                f.write(orjson.dumps(self._state.model_dump()))
        except OSError as e:
            logging.error("Error saving application state: %s", e)

    @property
    def current_state(self) -> AppState:
        return self._state

    def update_symbol(self, symbol: str):
        self._state.last_symbol = symbol
        self.save_state()

    def update_timeframe(self, timeframe: str):
        self._state.last_timeframe = timeframe
        self.save_state()


# A single instance for the application to use.
APP_DATA_DIR = Path.home() / ".cryptochart"
state_manager = StateManager(APP_DATA_DIR / "app_state.json")