#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

# from abots.net import SocketServer, SocketClient
# from abots.ui import TUI

# tui = TUI()

# from abots.events import Proxy

# class Counter(object):
#     def __init__(self):
#         self._value = 0
        
#     def update(self, value):
#         self._value = self._value + value

#     def get_value(self):
#         return self._value

#     def __str__(self):
#         return "Counter"

# modules = list()
# modules.append(Counter)
# proxy = Proxy(modules)

# from abots.events.event import Event
# from abots.events.proc import Proc
# from abots.events import Every

# from time import time, sleep
# from multiprocessing import Queue, Process, Manager

# event_q = Queue()
# # send_q = Queue()
# timeout = 0.02

# def nag(eq):
#     eq.put(time())

# def blab(eq):
#     print(eq.get(block=True, timeout=timeout))

# def destroy(everys, queues):
#     for every in everys:
#         every.stop()
#     for queue in queues:
#         queue.close()
#         queue.join_thread()

# nag_every = Every(10, nag, event_q)
# nag_proc = Process(target=nag_every.start)

# blab_every = Every(10, blab, event_q)
# blab_proc = Process(target=blab_every.start)

# everys = [
#     nag_every,
#     blab_every
# ]

# queues = [event_q]

# nag_proc.start()
# blab_proc.start()

from abots.events import Processor

class Test:
    def __init__(self, condition, events):
        self.counter = 0
        self.condition = condition
        self.events = events

    def handler(self, event):
        print(event)
        self.counter = self.counter + 1

    def start(self):
        print("Started")

    def stop(self):
        print("Stopped")