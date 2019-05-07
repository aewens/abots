#!env/bin/python3

from abots.events import Duodecimer, Cron
from abots.helpers import eprint, cast, Logger

from queue import Queue, Empty
from threading import Event, Lock
from time import sleep, time

intervals = ["5s", "30s", "1m"]

def fib(n):
    if n <= 1:
        return 1
    return fib(n - 1) + fib(n - 2)

def fibber(n, log):
    log.debug("Starting fibber")
    result = fib(10 + n)
    when = str(int(time()))[-3:]
    log.debug(f"Timer {intervals[n % 3]} :{when}: {result}")

timers = Duodecimer()
timers.start()
log = Logger("test_abots", settings={"disabled": ["file"]})
log.start()
for i in range(15):
    timers.assign(intervals[i % 3], fib, (10 + i,))
triggers = dict()
triggers["time"] = Cron.next_minutes(1)
cron = Cron(False, triggers)
timers.schedule(cron, fibber, (15, log))
log.info("Done submitting")
sleep(60 * 3 + 5)
log.info("Stopping...")
log.stop()
timers.stop()
