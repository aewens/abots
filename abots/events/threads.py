from abots.helpers import eprint, cast
from abots.events import Every

from queue import Queue, Empty, Full
from threading import Thread, Event, Lock, RLock, BoundedSemaphore

"""
TODO:
- Add routine clean-up in ThreadPoolManager of un-used thread pools
"""

class ThreadPool:
    def __init__(self, pool_size, timeout=None):
        self.locks = list()
        self.events = list()
        self.queues = list()
        self.workers = list()
        data = dict()
        for s in range(pool_size):
            lock = Lock()
            event = Event()
            queue = Queue()
            args = (s, event, queue, timeout)
            worker = Thread(target=self._worker, args=args)
            worker.setDaemon(True)
            self.locks.append(lock)
            self.events.append(event)
            self.queues.append(queue)
            self.workers.append(worker)
            worker.start()

    def _worker(self, worker_id, event, queue, timeout=None):
        while not event.is_set():
            try:
                # print(f"[{self.tid}]: Getting task")
                if timeout is not None:
                    job = queue.get(block=True, timeout=timeout)
                else:
                    job = queue.get_nowait()
                if len(job) != 2:
                    # print(f"[worker:{worker_id}]: Job is malformed")
                    continue
                controls, task = job
                if len(controls) != 3:
                    # print(f"[worker:{worker_id}]: Controls are malformed")
                    continue
                done, semaphore, lock = controls
                if task is None: # NOTE: Poison pill to kill worker
                    # print(f"[worker:{worker_id}]: Poisoned")
                    event.set()
                    done.set()
                    lock.release()
                    semaphore.release()
                    break
                if len(task) != 3:
                    # print(f"[worker:{worker_id}]: Task is malformed")
                    done.set()
                    lock.release()
                    semaphore.release()
                    continue
                method, args, kwargs = task
                # print(f"[{self.tid}]: Running task")
                try:
                    method(*args, **kwargs)
                except Exception as e:
                    print(e)
                finally:
                    done.set()
                    lock.release()
                    semaphore.release()
                    queue.task_done()
            except Empty:
                continue
        # Clear out the queue
        # print(f"[worker:{worker_id}]: Clearing out queue")
        while True:
            try:
                queue.get_nowait()
                queue.task_done()
            except Empty:
                break

    def stop(self, done=None, wait=True):
        # print(f"Stopping pool")
        for event in self.events:
            event.set()
        if wait:
            for worker in self.workers:
                worker.join()
        cast(done, "set")
        # print(f"Stopped pool")

class ThreadPoolManager:
    def __init__(self, pool_size, cleanup=-1, timeout=None):
        self.pool_size = pool_size
        self.timeout = timeout
        self.cleanup = cleanup
        self.pool_cursor = 0
        self.worker_cursor = 0
        self.pools = list()
        self.locks = list()
        self.events = list()
        self.queues = list()
        self.workers = list()
        self.semaphores = list()
        self._manager = Lock() # NOTE: Maybe make this an RLock?
        self.stopped = Event()
        self._add_pool()
        if self.cleanup > 0:
            self.cleaner = Every(self.cleanup, self._cleaner)

    def _next_pool(self):
        self.pool_cursor = (self.pool_cursor + 1) % len(self.pools)

    def _next_worker(self):
        self.worker_cursor = (self.worker_cursor + 1) % self.pool_size
        # NOTE: This is a potential optimization for later
        # if self.worker_cursor == 0:
        #     self._next_pool()

    def _cleaner(self):
        if len(self.pools) == 0 or self._manager.locked():
            return # Try again later
        with self._manager:
            pools = list()
            for pool_index in range(1, len(self.pools) - 1):
                pool = self.pools[pool_index]
                queues = self.queues[pool_index]
                idle = any([queue.empty() for queue in queues])
                if not idle:
                    continue
                pools.append(pool)
            for pool in pools:
                self._stop_pool(pool)

    def _stop_pool(self, pool, done=None, wait=True):
        index = self.pools.index(pool)
        # print(f"[manager] Stopping pool {index}")
        lock = self.locks[index]
        event = self.events[index]
        queue = self.queues[index]
        worker = self.workers[index]
        semaphore = self.semaphores[index]
        self.pools.remove(pool)
        self.locks.remove(lock)
        self.events.remove(event)
        self.queues.remove(queue)
        self.workers.remove(worker)
        self.semaphores.remove(semaphore)
        pool.stop(done, wait)
        # print(f"[manager] Stopped pool {index}")

    def _add_pool(self):
        index = len(self.pools)
        # print(f"[manager] Adding pool {index}")
        pool = ThreadPool(self.pool_size, self.timeout)
        self.pools.append(pool)
        self.locks.append(pool.locks)
        self.events.append(pool.events)
        self.queues.append(pool.queues)
        self.workers.append(pool.workers)
        self.semaphores.append(BoundedSemaphore(self.pool_size))
        return index

    def add_pool(self):
        with self._manager:
            self._add_pool()

    def wait(self):
        # print("[manager] Waiting on workers in pools")
        with self._manager:
            for pool in self.pools:
                for worker in pool.workers:
                    worker.join()
    
    def stop(self, wait=True):
        # print("[manager] Stopping")
        if self.cleanup > 0:
            self.cleaner.event.set()
        with self._manager:
            dones = list()
            threads = list()
            for pool in self.pools:
                done = Event()
                dones.append(done)
                thread = Thread(target=pool.stop, args=(done, wait))
                thread.setDaemon(True)
                threads.append(thread)
                thread.start()
            if wait:
                for thread in threads:
                    thread.join(self.timeout)
            cast(self.stopped, "set")
        # print("[manager] Stopped")

    def reserve(self, method, args=tuple(), kwargs=dict(), reserve=True):
        done = Event()
        # print("[manager:reserve] Acquiring lock")
        with self._manager:
            task = method, args, kwargs
            if self.pool_cursor >= len(self.pools):
                self._next_pool()
            pool_found = False
            for p in range(len(self.pools)):
                # print(f"[manager:reserve] Trying pool {self.pool_cursor}")
                semaphore = self.semaphores[self.pool_cursor]
                if not semaphore.acquire(False):
                    self._next_pool()
                    continue
                pool_found = True
                break
            if not pool_found:
                # print(f"[manager:reserve] Pools are full, adding new pool")
                index = self._add_pool()
                self.pool_cursor = index
                self.worker_cursor = 0
                semaphore = self.semaphores[self.pool_cursor]
                semaphore.acquire()
            # print(f"[manager:reserve] Using pool {self.pool_cursor}")
            pool = self.pools[self.pool_cursor]
            for w in range(self.pool_size):
                # print(f"[manager:reserve] Trying worker {self.worker_cursor}")
                lock = self.locks[self.pool_cursor][self.worker_cursor]
                event =self.events[self.pool_cursor][self.worker_cursor]
                queue =self.queues[self.pool_cursor][self.worker_cursor]
                if event.is_set() or lock.locked():
                    self._next_worker()
                    continue
                if not reserve:
                    lock = Lock()
                # print(f"[manager:reserve] Using worker {self.worker_cursor}")
                lock.acquire()
                controls = done, semaphore, lock
                job = controls, task
                queue.put_nowait(job)
                self._next_worker()
                break
        return done
