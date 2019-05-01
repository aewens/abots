"""

events/Shared
=============

This is a simple wrapper around the multiprocessing manager queue for safe 
usage of its functions when considering dangling entries during closing or 
empty/full events preventing getting / putting entries.

"""

from queue import Empty, Full
from multiprocessing import get_context

class Shared:
    def __init__(self, queue):
        self.queue = queue

    def empty(self):
        return self.queue.empty()

    def done(self):
        return self.queue.task_done()

    def safe_get(self, timeout=None):
        try:
            if timeout is None:
                return self.queue.get(block=False)
            else:
                return self.queue.get(block=True, timeout=timeout)
        except Empty:
            return None

    def safe_put(self, entry, timeout=None):
        try:
            self.queue.put(entry, block=False, timeout=timeout)
            return True
        except Full:
            return False

    def safe_apply(self, action, timeout=None, *args, **kwargs):
        entry = self.safe_get(timeout)
        result = action(entry, *args, **kwargs)
        self.done()
        return result

    def gather(self, timeout=None):
        while not self.queue.empty():
            # Use yield to allow generators to gather entries with timeouts
            yield self.queue.safe_get(timeout)

    def safe_close(self):
        # Gather all leftover messages still in the queue
        gathered = (entry for entry in self.gather())
        # self.queue.join()
        return gathered