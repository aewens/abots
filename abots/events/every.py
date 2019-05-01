from time import monotonic, sleep
from threading import Event, Thread

class Every:
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.event = Event()

    def _wrapper(self, *args, **kwargs):
        start = monotonic()
        while not self.event.is_set():
            self.function(*args, **kwargs)
            sleep(self.interval - ((monotonic() - start) % self.interval))

    def start(self):
        thread = Thread(target=self._wrapper, args=args, kwargs=kwargs)
        thread.setDaemon(True)
        thread.start()

    def stop(self):
        self.event.set()