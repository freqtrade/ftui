from textual import on
from textual.events import ScreenResume, ScreenSuspend
from textual.screen import Screen


class TimedScreen(Screen):
    timers = {}

    def register_timer(self, name, timer):
        self.timers[name] = timer

    @on(ScreenSuspend)
    def pause_timers(self):
        for ts in self.timers.keys():
            print(f"Pausing {ts}")
            self.timers[ts].pause()

    @on(ScreenResume)
    def resume_timers(self):
        for ts in self.timers.keys():
            print(f"Resuming {ts}")
            self.timers[ts].resume()
