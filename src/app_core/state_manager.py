import orjson
from pathlib import Path
from pydantic import BaseModel, Field

# Define the structure of our persistent state
class AppState(BaseModel):
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
            with open(self._file_path, 'rb') as f:
                data = orjson.loads(f.read())
                return AppState(**data)
        except (orjson.JSONDecodeError, TypeError, ValueError):
            # If file is corrupt or malformed, start with a default state
            return AppState()

    def save_state(self):
        """Saves the current state to the JSON file."""
        try:
            # Ensure parent directory exists
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, 'wb') as f:
                f.write(orjson.dumps(self._state.model_dump()))
        except IOError as e:
            # Handle cases where we can't write to the file
            print(f"Error saving state: {e}")

    @property
    def current_state(self) -> AppState:
        return self._state

    def update_symbol(self, symbol: str):
        self._state.last_symbol = symbol
        self.save_state()

    def update_timeframe(self, timeframe: str):
        self._state.last_timeframe = timeframe
        self.save_state()

# Create a default instance for the application to use.
# The path can be made platform-specific in a real app (e.g., using appdirs).
APP_DATA_DIR = Path.home() / ".cryptochart"
state_manager = StateManager(APP_DATA_DIR / "app_state.json")