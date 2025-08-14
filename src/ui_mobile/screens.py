from collections import deque
from datetime import datetime
from decimal import Decimal

from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.screenmanager import Screen
from kivy_garden.graph import LinePlot

from src.app_core.config import config
from src.schemas.market_data_pb2 import AggregatedDataPoint, Candle


class ChartScreen(Screen):
    graph_widget = ObjectProperty(None)
    price_label = ObjectProperty(None)
    symbol_label = ObjectProperty(None)
    timeframe_spinner = ObjectProperty(None)
    current_symbol = StringProperty("")
    current_timeframe = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = App.get_running_app().controller
        self.state = App.get_running_app().state
        self._data_buffer = deque(maxlen=100)
        self.price_plot = None
        self.vwap_plot = None

    def on_enter(self, *args):
        """Called when the screen is displayed."""
        self.symbol_label.text = self.current_symbol

    def load_initial_data(self):
        """Load the last saved state and fetch initial data."""
        self.current_symbol = self.state.last_symbol
        self.current_timeframe = self.state.last_timeframe

        if not self.price_plot:
            self.price_plot = LinePlot(color=[0, 1, 0, 1], line_width=2)
            self.vwap_plot = LinePlot(color=[0, 1, 1, 1], line_width=1.5)
            self.graph_widget.add_plot(self.price_plot)
            self.graph_widget.add_plot(self.vwap_plot)

        self.timeframe_spinner.text = self.current_timeframe
        self.controller.switch_symbol(self.current_symbol)
        self.controller.load_historical_data(
            self.current_symbol, self.current_timeframe
        )

    def on_timeframe_select(self, timeframe: str):
        """Called when a new timeframe is selected from the spinner."""
        if self.current_timeframe != timeframe:
            self.current_timeframe = timeframe
            App.get_running_app().state.last_timeframe = timeframe
            self.clear_chart()
            self.controller.load_historical_data(
                self.current_symbol, self.current_timeframe
            )

    def set_historical_data(self, candles: list[Candle]):
        self.clear_chart()
        for candle in candles:
            ts = datetime.fromisoformat(candle.open_time_utc).timestamp()
            price = float(Decimal(candle.close))
            self._data_buffer.append({"time": ts, "price": price, "vwap": 0})
        self.plot_data()

    def update_data(self, data_point: AggregatedDataPoint):
        if (data_point.symbol == self.current_symbol and
                data_point.timeframe == self.current_timeframe):
            ts = datetime.fromisoformat(data_point.timestamp_utc).timestamp()
            price = float(Decimal(data_point.last_price))
            vwap = float(Decimal(data_point.vwap))
            new_point = {"time": ts, "price": price, "vwap": vwap}

            if self._data_buffer and self._data_buffer[-1]["time"] == ts:
                self._data_buffer[-1] = new_point
            else:
                self._data_buffer.append(new_point)

            self.price_label.text = f"{price:.2f}"
            self.plot_data()

    def plot_data(self):
        if not self._data_buffer:
            return

        points = list(self._data_buffer)
        price_points = [(p["time"], p["price"]) for p in points]
        vwap_points = [(p["time"], p["vwap"]) for p in points if p.get("vwap")]

        self.price_plot.points = price_points
        if vwap_points:
            self.vwap_plot.points = vwap_points

        min_price = min(p[1] for p in price_points)
        max_price = max(p[1] for p in price_points)
        self.graph_widget.ymin = min_price * 0.98
        self.graph_widget.ymax = max_price * 1.02
        self.graph_widget.xmin = price_points[0][0]
        self.graph_widget.xmax = price_points[-1][0]

    def clear_chart(self):
        self._data_buffer.clear()
        self.price_plot.points = []
        self.vwap_plot.points = []


class SettingsScreen(Screen):
    symbols_rv = ObjectProperty(None)

    def on_enter(self, *args):
        # Populate the RecycleView with available symbols
        self.symbols_rv.data = [
            {"text": symbol} for symbol in config.exchange_integrations.keys()
        ]

    def select_symbol(self, symbol: str):
        chart_screen = self.manager.get_screen("chart")
        if chart_screen.current_symbol != symbol:
            chart_screen.current_symbol = symbol
            chart_screen.clear_chart()

            controller = App.get_running_app().controller
            controller.switch_symbol(symbol)
            controller.load_historical_data(symbol, chart_screen.current_timeframe)

        self.manager.current = "chart"