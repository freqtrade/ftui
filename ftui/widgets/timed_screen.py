from textual import on
from textual.events import ScreenResume, ScreenSuspend
from textual.screen import Screen


class TimedScreen(Screen):
    timers = {}

    @on(ScreenSuspend)
    def pause_timers(self):
        for ts in self.timers.keys():
            print(f"Pausing {self.id} {ts}")
            self.timers[ts].pause()

    @on(ScreenResume)
    def resume_timers(self):
        for ts in self.timers.keys():
            print(f"Resuming {self.id} {ts}")
            self.timers[ts].resume()
