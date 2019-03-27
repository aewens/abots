from time import monotonic, sleep
from multiprocessing import Event, Process

class Every:
    def __init__(self, interval, function, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.interval = interval
        self.function = function
        self.condition = Event()

    def _wrapper(self):
        start = monotonic()
        while not self.condition.is_set():
            self.function(*self.args, **self.kwargs)
            sleep(self.interval - ((monotonic() - start) % self.interval))

    def start(self):
        proc = Process(target=self._wrapper)
        proc.start()

    def stop(self):
        self.condition.set()