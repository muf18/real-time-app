# Real-Time Crypto Charting Client

This project is a high-performance, real-time, cross-platform cryptocurrency charting client built in Python. It connects directly to exchange WebSocket APIs to aggregate and display live trade data with sub-300ms latency.

## Architecture Overview

The application is architected with a clean separation between the core business logic and the user interface, allowing it to target both desktop (Windows, macOS) and mobile (Android) platforms from a shared codebase.

- **`src/app_core`**: The heart of the application, containing all the non-UI logic. It's built entirely on Python's `asyncio` framework for high-performance, non-blocking I/O. It handles WebSocket connections, data normalization (JSON to Protobuf), real-time aggregation (VWAP, Volume), and historical data fetching.
- **`src/ui_desktop`**: The desktop UI implemented with **PySide6** and **PyQtGraph**. It subscribes to the `app_core` for live data updates and provides a rich, responsive charting experience.
- **`src/ui_mobile`**: The mobile UI implemented with **Kivy**. It connects to the same `app_core` and is optimized for touch-based interaction on Android devices.
- **CI/CD**: A fully automated, production-grade CI/CD pipeline is defined in `.github/workflows/main.yml`. It handles linting, testing, building, signing, and releasing for all target platforms.

## Features

- **Low Latency**: p99 latency from socket read to chart render is under 300ms.
- **Multi-Exchange Aggregation**: Real-time trade data is aggregated from multiple exchanges.
- **Real-Time Analytics**: On-the-fly VWAP and cumulative volume calculation.
- **Cross-Platform**: Single codebase for Windows, macOS (Intel/Apple Silicon), and Android.
- **Resilient Networking**: Automatic WebSocket reconnection with exponential backoff.
- **Secure**: API keys are stored securely using the native OS credential manager (`keyring`).

## Getting Started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd cryptochart
    ```

2.  **Install dependencies:**
    - For desktop development:
      ```bash
      poetry install --with dev --extras "desktop"
      ```
    - For mobile development:
      ```bash
      poetry install --with dev --extras "mobile"
      ```

3.  **Generate Protobuf schemas:**
    ```bash
    poetry run python -m grpc_tools.protoc -I=src/schemas --python_out=src/schemas src/schemas/market_data.proto
    # Create the __init__.py to make it a package
    touch src/schemas/__init__.py
    ```

### Running the Application

- **Desktop:**
  ```bash
  poetry run python src/ui_desktop/main.py