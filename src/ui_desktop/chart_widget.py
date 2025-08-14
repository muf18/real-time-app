from collections import deque
from decimal import Decimal
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView, QVBoxLayout, QWidget
from datetime import datetime, timezone

from src.schemas.market_data_pb2 import AggregatedDataPoint, Candle

# Set pyqtgraph options for better performance and appearance
pg.setConfigOptions(antialias=True, useOpenGL=True)

class CandlestickItem(pg.GraphicsObject):
    """Custom GraphicsObject for displaying candlestick data."""
    def __init__(self, data):
        pg.GraphicsObject.__init__(self)
        self.data = data  # data must be a list of dicts with keys: (time, open, high, low, close)
        self.generatePicture()

    def generatePicture(self):
        self.picture = pg.QtGui.QPicture()
        p = pg.QtGui.QPainter(self.picture)
        w = (self.data[1]['time'] - self.data[0]['time']) / 2.
        for candle in self.data:
            # Green for price up, Red for price down
            pen_color = (0, 200, 0) if candle['close'] >= candle['open'] else (200, 0, 0)
            p.setPen(pg.mkPen(color=pen_color))
            p.setBrush(pg.mkBrush(color=pen_color))
            # Draw wick
            p.drawLine(pg.QtCore.QPointF(candle['time'], candle['low']), pg.QtCore.QPointF(candle['time'], candle['high']))
            # Draw body
            if candle['open'] != candle['close']:
                p.drawRect(pg.QtCore.QRectF(candle['time'] - w, candle['open'], w * 2, candle['close'] - candle['open']))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return pg.QtCore.QRectF(self.picture.boundingRect())

class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)

        self._setup_plots()

    def _setup_plots(self):
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getPlotItem().setAxisItems({'bottom': pg.DateAxisItem()})

        # Main price plot
        self.price_plot = self.plot_widget.getPlotItem()
        self.price_plot.setLabel('left', 'Price')

        # Volume plot (linked X-axis)
        self.volume_plot = pg.PlotItem()
        self.price_plot.scene().addItem(self.volume_plot)
        self.price_plot.getViewBox().sigResized.connect(self._update_volume_plot_geometry)
        self.volume_plot.getAxis('left').setLabel('Volume')
        self.price_plot.getAxis('bottom').linkToView(self.volume_plot.getViewBox())
        
        self.candle_item = None
        self.vwap_item = self.price_plot.plot(pen=pg.mkPen('c', width=2), name="VWAP")
        self.volume_bar_item = pg.BarGraphItem(x=[], height=[], width=0.8, brush='w')
        self.volume_plot.addItem(self.volume_bar_item)
        
        # Horizontal line for the last price
        self.last_price_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('y', style=Qt.DotLine))
        self.price_plot.addItem(self.last_price_line)

        self._data_buffer = deque(maxlen=500)

    def _update_volume_plot_geometry(self):
        """Keeps the volume plot positioned correctly below the price plot."""
        vb = self.price_plot.getViewBox()
        p_rect = vb.sceneBoundingRect()
        self.volume_plot.setGeometry(p_rect)
        # Set the volume plot to occupy the bottom 25% of the area
        vb.setLimits(yMin=0) # prevent panning below zero
        volume_height_ratio = 0.25
        self.price_plot.setLimits(yMin=0)
        self.price_plot.getViewBox().setYRange(0, 1, padding=0)
        self.volume_plot.getViewBox().setYRange(0, 1, padding=0)
        
    def update_data(self, data_point: AggregatedDataPoint):
        """Updates the chart with a new aggregated data point."""
        ts = datetime.fromisoformat(data_point.timestamp_utc).timestamp()
        
        new_candle = {
            'time': ts,
            'open': float(Decimal(data_point.open_price)),
            'high': float(Decimal(data_point.high_price)),
            'low': float(Decimal(data_point.low_price)),
            'close': float(Decimal(data_point.last_price)),
            'volume': float(Decimal(data_point.cumulative_volume)),
            'vwap': float(Decimal(data_point.vwap))
        }

        if self._data_buffer and self._data_buffer[-1]['time'] == ts:
            self._data_buffer[-1] = new_candle
        else:
            self._data_buffer.append(new_candle)
            
        self.plot_data()
        self.last_price_line.setPos(new_candle['close'])

    def set_historical_data(self, candles: List[Candle]):
        """Clears existing data and populates the chart with historical candles."""
        self._data_buffer.clear()
        for candle in candles:
            self._data_buffer.append({
                'time': datetime.fromisoformat(candle.open_time_utc).timestamp(),
                'open': float(Decimal(candle.open)),
                'high': float(Decimal(candle.high)),
                'low': float(Decimal(candle.low)),
                'close': float(Decimal(candle.close)),
                'volume': float(Decimal(candle.volume)),
                'vwap': 0 # VWAP not available in historical data
            })
        self.plot_data()

    def plot_data(self):
        """(Re)draws all chart items based on the current data buffer."""
        if not self._data_buffer:
            return

        data = list(self._data_buffer)
        times = [d['time'] for d in data]
        volumes = [d['volume'] for d in data]
        vwaps = [d['vwap'] for d in data if d.get('vwap')]

        if self.candle_item:
            self.price_plot.removeItem(self.candle_item)
        
        self.candle_item = CandlestickItem(data)
        self.price_plot.addItem(self.candle_item)
        
        if vwaps:
             self.vwap_item.setData(x=times[-len(vwaps):], y=vwaps)

        candle_width = (times[1] - times[0]) if len(times) > 1 else 60
        self.volume_bar_item.setOpts(x=times, height=volumes, width=candle_width * 0.8)

    def clear_chart(self):
        self._data_buffer.clear()
        if self.candle_item:
            self.price_plot.removeItem(self.candle_item)
            self.candle_item = None
        self.vwap_item.clear()
        self.volume_bar_item.setOpts(x=[], height=[])
        self.last_price_line.setPos(0)