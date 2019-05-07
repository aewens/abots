from time import monotonic, sleep
from threading import Event, Thread

class Every:
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.event = Event()

    def _wrapper(self, *args, **kwargs):
        start = monotonic()
        state = None
        while not self.event.is_set():
            state = self.function(state, *args, **kwargs)
            sleep(self.interval - ((monotonic() - start) % self.interval))

    def start(self):
        args = self.args
        kwargs = self.kwargs
        thread = Thread(target=self._wrapper, args=args, kwargs=kwargs)
        thread.setDaemon(True)
        thread.start()
        return thread

    def stop(self):
        self.event.set()