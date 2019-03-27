from queue import Empty, Full
from multiprocessing import get_context
import multiprocessing.queues import Queue as MPQueue

class Shared(MPQueue):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, ctx=get_context())

    def safe_get(self, timeout=None):
        try:
            if timeout is None:
                return self.get(block=False)
            else:
                return self.get(block=True, timeout=timeout)
        except Empty:
            return None

    def safe_put(self, entry, timeout=None):
        try:
            self.put(entry, block=False, timeout=timeout)
            return True
        except Full:
            return False

    def gather(self, timeout=None):
        while not self.empty():
            yield self.safe_get(timeout)

    def safe_close(self):
        closed = sum(1 for entry in self.gather())
        self.close()
        self.join_thread()
        return closed