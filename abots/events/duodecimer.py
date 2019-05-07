from abots.events import Every, ThreadMarshal
from abots.helpers import cast, utc_now

from queue import Queue, Empty
from collections import defaultdict
from threading import Thread

"""

TODO:
* Add way to export tasks to pickle file on stop?

Duodecimer: "duodec-" meaning twelve and the "-imer" for timer, or twelve timers

Will be a scheduler running 12 threads of the increments of time:
* 1 second
* 30 seconds
* 1 minute
* 5 minutes
* 10 minutes
* 15 minutes
* 30 minutes
* 1 hour
* 1 day
* 1 week
* 1 fortnight (2 weeks)
* cron

The cron being a thread that triggers tasks when a date/time trigger occurs 
(with 1 minute precision, but run outside the 1 minute thread). Triggers by:
* Specific times in specific dates
* Specific times every day
* Change in the week day
* Change in the month
* Change in the year

"""

minutes_in_seconds = 60
hour_in_seconds = 60 * minutes_in_seconds
day_in_seconds = 24 * hour_in_seconds
week_in_seconds = 7 * day_in_seconds
fortnight_in_seconds = 2 * week_in_seconds

class Cron:
    def __init__(self, repeat, triggers):
        self.repeat = repeat
        self.triggers = triggers
        # self.start = utc_now()
        # self.date = self.get_date(self.start)
        # self.time = self.get_time(self.start)
        # self.weekday = self.get_weekday(self.start)
        # self.day = self.get_day(self.start)
        # self.month = self.get_month(self.start)
        # self.year = self.get_year(self.start)
    
    @staticmethod
    def get_date(when=None):
        if when is None:
            when = utc_now()
        return int(f"{when.year}{when.month:02}{when.day:02}")
    
    @staticmethod
    def get_time(when=None):
        if when is None:
            when = utc_now()
        return int(f"{when.hour:02}{when.minute:02}")
    
    @staticmethod
    def get_weekday(when=utc_now()):
        return when.weekday()
    
    @staticmethod
    def get_day(when=utc_now()):
        return when.day
    
    @staticmethod
    def get_month(when=utc_now()):
        return when.month
    
    @staticmethod
    def get_year(when=utc_now()):
        return when.year

    @staticmethod
    def next_minutes(minutes):
        now = utc_now()
        hour = now.hour
        minute = now.minute + minutes
        if minute >= 60:
            hour = 0 if hour == 23 else hour + 1
            minute = minute % 60
        return int(f"{hour:02}{minute:02}")

    @staticmethod
    def next_hours(hours):
        now = utc_now()
        minute = now.minute
        hour = now.hour + hours
        if hour >= 24:
            hour = hour % 24
        return int(f"{hour:02}{minute:02}")
        


class Duodecimer:
    def __init__(self):
        self.queues = dict()
        self.timers = dict()
        self._intervals = dict()
        self._intervals["5s"] = 5
        self._intervals["30s"] = 30
        self._intervals["1m"] = minutes_in_seconds
        self._intervals["5m"] = 5 * minutes_in_seconds
        self._intervals["10m"] = 10 * minutes_in_seconds
        self._intervals["15m"] = 15 * minutes_in_seconds
        self._intervals["30m"] = 30 * minutes_in_seconds
        self._intervals["1h"] = hour_in_seconds
        self._intervals["1d"] = day_in_seconds
        self._intervals["1w"] = week_in_seconds
        self._intervals["1f"] = fortnight_in_seconds
        self._load()

    def _load(self):
        for name, interval in self._intervals.items():
            queue = Queue()
            timer = Every(interval, self._timer, queue)
            self.queues[name] = queue
            self.timers[name] = timer
        cron_queue = Queue()
        cron_timer = Every(minutes_in_seconds, self._cron, cron_queue)
        self.queues["cron"] = cron_queue
        self.timers["cron"] = cron_timer

    def _process_queue(self, state, queue, task_size):
        if state is None:
            state = list()
        while True:
            try:
                task = queue.get_nowait()
                if len(task) != task_size:
                    # print(f"[worker:{worker_id}]: Task is malformed")
                    continue
                state.append(task)
                queue.task_done()
            except Empty:
                break
        return state

    def _process_trigger(self, unit, previous, value):
        now = cast(Cron, f"get_{unit}", utc_now())
        if value == "change" and previous is not None:
            return cast(Cron, f"get_{unit}", previous) != now
        else:
            return now == value

    def _timer(self, state, queue):
        state = self._process_queue(state, queue, 3)
        marshal = ThreadMarshal(len(state), destroy=True)
        for task in state:
            # print(f"[worker:{worker_id}]: Running task")
            marshal.reserve(*task)
        return state

    def _cron(self, state, queue):
        if state is None:
            state = defaultdict(lambda: None)
        state["tasks"] = self._process_queue(state["tasks"], queue, 4)
        previous = state["previous"]
        removing = list()
        for task in state["tasks"]:
            cron, target, args, kwargs = task
            assert isinstance(cron.triggers, dict), "Expected dict"
            triggered = list()
            for trigger, value in cron.triggers.items():
                if trigger == "date":
                    triggered.append(Cron.get_date() >= value)
                elif trigger == "time":
                    triggered.append(Cron.get_time() >= value)
                elif trigger in ["weekday", "day", "month", "year"]:
                    processed = self._proccess_trigger(trigger, previous, value)
                    triggered.append(processed)
                else:
                    continue
            if all(triggered):
                thread = Thread(target=target, args=args, kwargs=kwargs)
                thread.start()
                if not cron.repeat:
                    removing.append(task)
        for task in removing:
            state["tasks"].remove(task)
        state["previous"] = utc_now()
        return state

    def start(self):
        for name, timer in self.timers.items():
            timer.start()

    def stop(self):
        for name, timer in self.timers.items():
            timer.stop()

    def assign(self, timer, method, args=tuple(), kwargs=dict()):
        if timer not in self.queues.keys():
            return None
        task = method, args, kwargs
        self.queues[timer].put(task)

    def schedule(self, cron, target, args=tuple(), kwargs=dict()):
        task = cron, target, args, kwargs
        self.queues["cron"].put(task)

"""

duodecimer = Duodecimer()
task_id = duodecimer.every(10, "minutes", task)
duodecimer.cancel(task_id)

"""
