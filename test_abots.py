#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

# from abots.ui import TUI

# tui = TUI()

# ========================

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

# ========================

# from abots.events import Proxy

# class Counter(object):
#     def __init__(self):
#         self._value = 0
        
#     def update(self, value):
#         self._value = self._value + value

#     def get(self):
#         return self._value

#     def __str__(self):
#         return "Counter"

# proxy = Proxy(Counter)

# ========================

# from abots.events import Processor, Every, Shared
# from time import sleep

# class Simple:
#     def __init__(self):
#         self.counter = 0

#     def handler(self, pipe, event):
#         self.counter = self.counter + 1
#         print(event, self.counter)
#         self.pipe.notify("complex", self.counter)

#     def start(self):
#         print("Started")

#     def stop(self):
#         print("Stopped")

# class Complex:
#     def __init__(self, pipe):
#         self.pipe = pipe
#         self.events = self.pipe.events
#         self.condition = self.pipe.condition
#         self.counter = 0
#         self.runner = Every(10, self.handler)

#     def handler(self):
#         self.pipe.notify("simple", self.counter)
#         events = Shared(self.events)
#         while not self.condition.is_set():
#             while not events.empty():
#                 self.counter = self.counter + 1
#                 event = events.safe_get()
#                 print(event, self.counter)
#                 events.done()
#                 self.pipe.notify("simple", self.counter)
#         self.stop()

#     def start(self):
#         print("Started")
#         self.pipe.listen("complex")
#         self.runner.start()

#     def stop(self):
#         print("Stopped")
#         if self.condition.is_set():
#             self.condition.set()
#         self.runner.stop()

# simple = Simple()

# processor = Processor()
# processor.start()

# processor.register(simple.handler, name="simple", simple=True)
# processor.register(Complex)

# processor.spinup_all()

# sleep(10)
# processor.stop()

# ========================

# from abots.events import Actor
# from abots.helpers import noop

# class Recaman:
#     def __init__(self, steps):
#         self.current = 0
#         self.steps = steps
#         self.seq = list()
#         self.seq.append(self.current)

#     def next(self):
#         step = len(self.seq)
#         if step == self.steps:
#             return None
#         backwards = self.current - step
#         if backwards > 0 and backwards not in self.seq:
#             self.current = backwards
#         else:
#             self.current = self.current + step
#         self.seq.append(self.current)
#         return self.current

# class Fibonacci:
#     def __init__(self, steps):
#         self.steps = steps
#         self.seq = [0, 1]

#     def next(self):
#         step = len(self.seq)
#         if step == self.steps:
#             return None
#         a, b = self.seq[-2:]
#         c = a + b
#         self.seq.append(c)
#         return c

# class Watcher:
#     def __init__(self, watching):
#         self.seqs = list()
#         self.done = list()
#         self.names = dict()
#         self.ready = False
#         for watch_id, name in enumerate(watching):
#             self.seqs.append(list())
#             self.done.append(False)
#             self.names[name] = watch_id

#     def receive(self, name, entry):
#         if self.ready:
#             return None
#         watch_id = self.names.get(name, None)
#         if watch_id is None:
#             return None
#         if entry is None:
#             self.done[watch_id] = True
#             if all(self.done):
#                 self.ready = True
#                 return True
#             return None
#         self.seqs[watch_id].append(entry)
#         return False

# class Cruncher:
#     def __init__(self):
#         self.seqs = None
#         self.seq = list()
#         self.step = 0

#     def load(self, seqs):
#         self.seqs = seqs

#     def next(self):
#         if self.seqs is None:
#             return None
#         steps = max(map(len, self.seqs))
#         if self.step == steps:
#             return None
#         entries = list()
#         for seq in self.seqs:
#             entries.append(seq[self.step])
#         state = self.average(entries)
#         print(state, entries)
#         self.seq.append(state)
#         return state
    
#     def average(self, entries):
#         return sum(entries) / len(entries)

#     def compute(self):
#         if self.seqs is None:
#             return None
#         running = True
#         while running:
#             running = False if self.next() is None else True
#         return self.seq
# steps = 15
# r = Recaman(steps)
# f = Fibonacci(steps)
# w = Watcher([r, f])
# c = Cruncher()

# def crunch(actor, message):
#    pass
# def collect(actor, message):
#     cpid, name, entry = message
#     status = w.receive(name, entry)
#     if status:
        
# procs = Manager().list()
# ac = Actor(crunch, procs)
# ar = Actor(noop, procs)
# af = Actor(noop, procs)
# aw = Actor(collect, procs)

# ar.start()
# af.start()
# aw.start()
# ac.start()

# ========================

# from multiprocessing import Process, Queue, Event, Manager
# from time import sleep
# from enum import Enum

"""

class Test(Actor):
    def __init__(self, name):
        super().__init__(name)

    def handler(self, code, header, message):
        result = message[::-1]
        if code == MailCode.NO_SENDER:
            return None
        from_pid, to_pid = header
        if code == MailCode.DELIVER:
            self.deliver(from_pid, to_pid, result)
        else:
            self.send(to_pid, result)

"""

# def basic(pid, handler):
#     print("go")
#     kill_switch, mailbox = supervisor.export(pid)
#     while not kill_switch.is_set():
#         while not mailbox.empty():
#             sleep(1)
#             handler = dict()
#             handler[MailCode.SENDER] = lambda s, r, m: supervisor.send(pid, r, m[::-1])
#             handler[MailCode.NO_SENDER] = lambda r, m: supervisor.send(pid, r, m[::-1])
#             handler[MailCode.DEFAULT] = lambda s, r, m: supervisor.send(pid, r, m[::-1])
#             header, message = supervisor.receive(mailbox, handler)
#     print("no")

# supervisor = Actor("__root__")

# pid1, proc1 = supervisor.spawn("a", basic, ("b"))
# pid2, proc2 = supervisor.spawn("b", basic, ("a"))

# proc1.start()
# proc2.start()

# supervisor.deliver("a", "Hello, world!")

# p1.start()
# p2.start()

# sleep(5)
# procs.stop()

# ========================

# import asyncio
# from time import time, monotonic

# begin = monotonic()

# # Awful on purpose
# def fib(n):
#     if n <= 1:
#         return 1
#     return fib(n - 1) + fib(n - 2)

# @asyncio.coroutine
# def coroutine(n):
#     print("Processing: Coroutine")
#     print("Starting: Part 1")
#     result1 = yield from part1(n)
#     print("Starting: Part 2")
#     result2 = yield from part2(n, result1)
#     return (result1, result2)

# @asyncio.coroutine
# def part1(n):
#     print("Processing: Part 1")
#     return fib(n)

# @asyncio.coroutine
# def part2(n, p1):
#     print("Processing: Part 2")
#     return p1 + fib(n)

# num = 30
# # print(fib(num))
# # print(fib(num))
# loop = asyncio.get_event_loop()
# try:
#     print("Starting")
#     coro = coroutine(num)
#     print("Looping")
#     value = loop.run_until_complete(coro)
#     print(f"Returning: {value}")
# finally:
#     print("Closing")
#     loop.close()
    
# print(f"{monotonic() - begin:.2f}s")

# def compute(name):
#     print(f"Starting {name} compute")
#     try:
#         while True:
#             message = (yield)
#             if name in message:
#                 result = sum(fib(30) for _ in range(len(message)))
#                 print(f"{name}[compute]: {result}")
#     except GeneratorExit:
#         print(f"Closing {name} compute")

# def reverse(name):
#     print(f"Starting {name} reverse")
#     try:
#         while True:
#             message = (yield)
#             if name in message:
#                 print(f"{name}[reverse]: {message[::-1]}")
#     except GeneratorExit:
#         print(f"Closing {name} reverse")

# def echo(name):
#     print(f"Starting {name} echo")
#     rn = reverse(name)
#     cn = compute(name)
#     next(rn)
#     next(cn)
#     try:
#         while True:
#             message = (yield)
#             rn.send(message)
#             cn.send(message)
#             if name in message:
#                 print(f"{name}[echo]: {message}")
#     except GeneratorExit:
#         print(f"Closing {name} echo")

# e1 = echo("test")
# next(e1)

# ========================

from abots.helpers import eprint, noop
from abots.events import Supervisor, Envelope
from abots.net import (SocketServer, SocketClient, SocketServerHandler, 
    SocketClientHandler)

from time import sleep

supervisor = Supervisor()

# (server, *a, **k), format|message|open_client|close_client|close
server = SocketServer("localhost", 10901, handler=SocketServerHandler)
# server_proc = Process(target=server)
server_actor = supervisor.spawn("server", server)

# (client, *a, **k), format|message|initialize
client = SocketClient("localhost", 10901, handler=SocketClientHandler)
# client_proc = Process(target=client.start)
client_actor = supervisor.spawn("client", client)

# server_proc.start()
# client_proc.start()
server_actor.start()
client_actor.start()

sleep(5)
print("Stopping")
supervisor.stop()
print("Stopped")