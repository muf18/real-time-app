from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QListWidget, QListWidgetItem, QComboBox, QToolBar

from src.app_core.config import config
from src.app_core.state_manager import state_manager
from src.schemas.market_data_pb2 import AggregatedDataPoint, Candle
from src.ui_desktop.chart_widget import ChartWidget
from src.ui_desktop.controller import UIController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Crypto Chart")
        self.setGeometry(100, 100, 1280, 720)

        # Initialize the controller
        self.controller = UIController()
        self.controller.new_aggregated_data.connect(self.on_new_data)
        self.controller.historical_data_loaded.connect(self.on_historical_data)

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout(central_widget)

        # Symbol list
        self.symbol_list = QListWidget()
        self.symbol_list.setMaximumWidth(200)
        for symbol in config.exchange_integrations.keys():
            self.symbol_list.addItem(QListWidgetItem(symbol))
        self.symbol_list.currentItemChanged.connect(self.on_symbol_changed)
        self.layout.addWidget(self.symbol_list)

        # Chart widget
        self.chart = ChartWidget()
        self.layout.addWidget(self.chart)
        
        # Toolbar for timeframe selection
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(config.supported_timeframes)
        self.timeframe_combo.currentTextChanged.connect(self.on_timeframe_changed)
        toolbar.addWidget(self.timeframe_combo)

        self._load_initial_state()

    def _load_initial_state(self):
        """Loads the last used symbol and timeframe from the state manager."""
        initial_state = state_manager.current_state
        
        # Set timeframe dropdown
        self.timeframe_combo.setCurrentText(initial_state.last_timeframe)
        
        # Set symbol list and trigger initial data load
        items = self.symbol_list.findItems(initial_state.last_symbol, Qt.MatchExactly)
        if items:
            self.symbol_list.setCurrentItem(items[0])
        else: # Fallback to the first item if last symbol isn't found
            self.symbol_list.setCurrentRow(0)

    def on_symbol_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            symbol = current.text()
            self.chart.clear_chart()
            self.controller.switch_symbol(symbol)
            self.controller.load_historical_data(symbol, self.timeframe_combo.currentText())
            
    def on_timeframe_changed(self, timeframe: str):
        state_manager.update_timeframe(timeframe)
        symbol = self.symbol_list.currentItem().text()
        if symbol:
            self.chart.clear_chart()
            self.controller.load_historical_data(symbol, timeframe)
            
    @Slot(AggregatedDataPoint)
    def on_new_data(self, data_point: AggregatedDataPoint):
        """Slot to handle new aggregated data from the controller."""
        if (data_point.symbol == self.symbol_list.currentItem().text() and
            data_point.timeframe == self.timeframe_combo.currentText()):
            self.chart.update_data(data_point)

    @Slot(list)
    def on_historical_data(self, candles: List[Candle]):
        """Slot to handle loaded historical data."""
        if candles:
            self.chart.set_historical_data(candles)

    def closeEvent(self, event):
        """Ensure a graceful shutdown on window close."""
        self.controller.shutdown()
        event.accept()