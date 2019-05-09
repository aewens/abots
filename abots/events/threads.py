from abots.helpers import eprint, cast
from abots.events import Every

from queue import Queue, Empty, Full
from threading import Thread, Event, Lock, RLock, BoundedSemaphore
from contextlib import contextmanager

"""
TODO:
"""

@contextmanager
def acquire_timeout(lock, timeout=-1):
    if timeout is None:
        timeout = -1
    result = lock.acquire(timeout=timeout)
    yield result
    if result:
        lock.release()

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

    def _exec_controls(self, controls):
        for action, methods in controls.items():
            for method in methods:
                cast(method, action)

    def _worker(self, worker_id, event, queue, timeout=None):
        while not event.is_set():
            try:
                # NOTE: This is really spammy, use only in case of emergencies
                # print(f"[worker:{worker_id}]: Getting task")
                if timeout is not None:
                    job = queue.get(block=True, timeout=timeout)
                else:
                    job = queue.get_nowait()
                if len(job) != 2:
                    # print(f"[worker:{worker_id}]: Job is malformed")
                    continue
                controls, task = job
                if type(controls) != dict:
                    # print(f"[worker:{worker_id}]: Controls are malformed")
                    continue
                if task is None: # NOTE: Poison pill to kill worker
                    # print(f"[worker:{worker_id}]: Poisoned")
                    event.set()
                    self._exec_controls(controls)
                    break
                if len(task) != 3:
                    # print(f"[worker:{worker_id}]: Task is malformed")
                    self._exec_controls(controls)
                    continue
                method, args, kwargs = task
                # print(f"[worker:{worker_id}]: Running task")
                try:
                    method(*args, **kwargs)
                except Exception as e:
                    print(e)
                finally:
                    # print(f"[worker:{worker_id}]: Task complete")
                    self._exec_controls(controls)
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

class ThreadMarshal:
    def __init__(self, pool_size, monitor=1, cleanup=True, timeout=None, 
        destroy=False):
        self.pool_size = pool_size
        self.monitor_interval = monitor
        self.cleanup = cleanup
        self.timeout = timeout
        self.destroy = destroy
        self.stopped = Event()
        self._manager = Lock() # NOTE: Maybe make this an RLock?
        self._load_presets()
        self._add_pool()

        if self.monitor_interval > 0:
            self.monitor = Every(self.monitor_interval, self._monitor)
            self.monitor.start()

    def _next_pool(self):
        self._pool_cursor = (self._pool_cursor + 1) % len(self.pools)

    def _next_worker(self):
        self._worker_cursor = (self._worker_cursor + 1) % self.pool_size
        # NOTE: This is a potential optimization for later
        # if self._worker_cursor == 0:
        #     self._next_pool()

    def _load_presets(self):
        self._pool_cursor = 0
        self._worker_cursor = 0
        self.pools = list()
        self.locks = list()
        self.events = list()
        self.queues = list()
        self.workers = list()
        self.semaphores = list()

    def _get_idle_pools(self):
        idle_pools = list()
        if len(self.pools) == 1:
            return idle_pools
        for index, queues in enumerate(self.queues):
            if index == 0:
                continue
            queues_empty = [queue.empty() for queue in queues]
            idle = all(queues_empty)
            if not idle:
                continue
            print(f"[manager] Pool {index} is idle")
            idle_pools.append(self.pools[index])
        return idle_pools

    def _monitor(self, state):
        # print("[manager] Cleaning pools")
        if self._manager.locked():
            return # Try again later
        with self._manager:
            idle_pools = self._get_idle_pools()
            if self.destroy and len(idle_pools) == len(self.pools):
                self.stop()
            elif self.cleanup and len(idle_pools) > 0:
                cleaning = Event()
                self._cleaner(idle_pools, cleaning)
                cleaning.wait()
        return None

    def _cleaner(self, idle_pools, done=None):
        print("[manager] Cleaning pools")
        for pool in idle_pools:
            self._stop_pool(pool, wait=done is not None)
        print("[manager] Pools are cleaned")
        cast(done, "set")

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

    def _run(self, task, controls, reserve, coordinates):
        pool_index, worker_index = coordinates
        # print(f"[manager:reserve] Trying worker {self.worker_index}")
        lock = self.locks[pool_index][worker_index]
        event =self.events[pool_index][worker_index]
        queue =self.queues[pool_index][worker_index]
        if event.is_set() or lock.locked():
            return False
        if not reserve:
            lock = Lock()
        # print(f"[manager:reserve] Using worker {worker_index}")
        lock.acquire()
        release = controls.get("release", list())
        release.append(lock)
        job = controls, task
        queue.put_nowait(job)
        return True

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

    def clean(self, done=None):
        with self._manager:
            idle_pools = self._get_idle_pools()
            if self.cleanup and len(idle_pools) > 0:
                self._cleaner(idle_pools, done)

    def wait(self):
        # print("[manager] Waiting on workers in pools")
        with self._manager:
            for pool in self.pools:
                for worker in pool.workers:
                    worker.join()
    
    def stop(self, wait=True):
        # print("[manager] Stopping")
        if self.monitor_interval > 0:
            self.monitor.event.set()
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
            self._load_presets()
            cast(self.stopped, "set")
        # print("[manager] Stopped")

    def run(self, task, done, reserve, coordinates):
        if len(task) != 3:
            return None
        if len(coordinates) != 2:
            return None
        method, args, kwargs = task
        if not callable(method) or type(args) != tuple or type(kwargs) != dict:
            return None
        pool_index, worker_index = coordinates
        if pool_index >= len(self.pools) or worker_index >= self.pool_size:
            return None
        with self.manager:
            semaphore = self.semaphores[pool_index]
            if not semaphore.acquire(False):
                return None
            controls = dict()
            controls["set"] = [done]
            controls["release"] = [sempahore]
            self._run(task, controls, reserve, coordinates)
        return True

    def reserve(self, method, args=tuple(), kwargs=dict(), reserve=True):
        # print("[manager:reserve] Acquiring lock")
        done = Event()
        with self._manager:
            task = method, args, kwargs
            if self._pool_cursor >= len(self.pools):
                self._next_pool()
            pool_found = False
            for p in range(len(self.pools)):
                # print(f"[manager:reserve] Trying pool {self._pool_cursor}")
                semaphore = self.semaphores[self._pool_cursor]
                if not semaphore.acquire(False):
                    self._next_pool()
                    continue
                pool_found = True
                break
            if not pool_found:
                # print(f"[manager:reserve] Pools are full, adding new pool")
                index = self._add_pool()
                self._pool_cursor = index
                self._worker_cursor = 0
                semaphore = self.semaphores[self._pool_cursor]
                semaphore.acquire()
            # print(f"[manager:reserve] Using pool {self._pool_cursor}")
            pool = self.pools[self._pool_cursor]
            for w in range(self.pool_size):
                coordinates = (self._pool_cursor, self._worker_cursor)
                controls = dict()
                controls["set"] = [done]
                controls["release"] = [semaphore]
                queued = self._run(task, controls, reserve, coordinates)
                self._next_worker()
                if not queued:
                    continue
                break
        return done
