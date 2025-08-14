from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager

from src.app_core.state_manager import state_manager
from src.ui_mobile.controller import KivyController
# Import screens to register them with the ScreenManager
from src.ui_mobile.screens import ChartScreen, SettingsScreen 

class CryptoChartApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = KivyController()
        self.state = state_manager.current_state

    def build(self):
        # The kv file is automatically loaded by Kivy if named cryptochart.kv
        # in the same directory as the App class.
        sm = ScreenManager()
        sm.add_widget(ChartScreen(name='chart'))
        sm.add_widget(SettingsScreen(name='settings'))
        return sm

    def on_start(self):
        """Called when the application starts."""
        self.controller.start()
        # Connect controller callbacks to the chart screen methods
        chart_screen = self.root.get_screen('chart')
        self.controller.on_new_data = chart_screen.update_data
        self.controller.on_historical_data = chart_screen.set_historical_data
        
        # Load initial data
        chart_screen.load_initial_data()

    def on_stop(self):
        """Called when the application is closed."""
        self.controller.shutdown()

if __name__ == '__main__':
    CryptoChartApp().run()