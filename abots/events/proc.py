"""

events\RawProc & events\Proc
============================

This is designed to be used run by events\Processor to allow it to control 
whatever class is sent to it. The class will be spawned inside of events\Proxy 
so that operate better in a multiprocessing environment. As well, they will be 
provided an event\Shared for an event queue as well as a multiprocessing event 
to trigger the stop condition.

"""
from abots.events.pipe import Pipe
from abots.events.shared import Shared
from abots.events import Every, Proxy
from abots.helpers import eprint

from multiprocessing import Event, Process, Manager
from traceback import print_exc
from time import sleep

# The logic in Proc will have full control of how to process events
class Proc(Process):
    def __init__(self, logic, exports, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

        # This is an optional handler used for logging
        self.handler = exports.get("handler", None)

        # How long to wait for condition before timing out
        self.timeout = exports.get("timeout", None)

        # This is just a wrapper around multiprocessing.Queue
        self.events = Shared()

        # This is used to indicate the stop condition for the process
        self.condition = Event()

        # The notifications that the process will listen to
        self.listeners = Manger().dict()
        
        # Pass along multiprocessing controls to exports for pipe
        exports["events"] = self.events
        exports["condition"] = self.condition
        exports["listeners"] = self.listeners

        # Controls the events sent to/received by the Processor
        self.pipe = Pipe(exports)

        # All actions needed for logic can be leveraged through the pipe
        self.logic = logic(self.pipe)

    # Works if, and only if, handler has an error method to call
    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)
        return True

    # Checks if method exists in logic, and if so calls it
    def call(self, method, *args, **kwargs):
        logic_method = getattr(self.logic, method, None)
        if logic_method is None:
            self._error("event\RawProc:call", method)
            return None
        return logic_method(*args, **kwargs)

    # This is launched with `start` because of the Process inheritance
    def run(self):
        try:
            status = self.call("start")
        except Exception:
            status = print_exc()
            eprint(status)
            self._error("event\RawProc:run", status)
            return None
        return status

    # Cleans up the multiprocessing components
    def stop(self):
        # Stop is called here so it can choose what to do with the queue
        # Once it is done, it should set the condition so the events can close
        try:
            status = self.call("stop")
        except Exception:
            status = print_exc()
            eprint(status)
            self._error("event\RawProc:stop", status)
            # If the condition was not already set, do it now
            if self.condition.is_set():
                self.condition.set()
        # Wait until logic is done with the events, then close the queue
        self.condition.wait(timeout=self.timeout)
        self.events.safe_close()
        return status

# A simplified version where logic will only process the event given
class SimpleProc(Proc):
    def __init__(self, logic, exports, *args, **kwargs):
        # While timeout is still used, it is used only in `run` here
        super().__init__(self, logic, exports, *args, **kwargs)
        
        # Since logic can be a function in Proc, it is not initalized here
        self.logic = logic

    # This is launched with `start` because of the Process inheritance
    def run(self):
        while not self.condition.is_set():
            while not self.events.empty():
                # The pipe is sent so logic can use it to react to the event
                self.logic(self.pipe, events.safe_get())
            # timeout is used here to add a delay in processing, if desired
            if self.timeout is not None:
                sleep(self.timeout)
    
    # Cleans up the multiprocessing components
    def stop(self):
        # If the condition was not already set, do it now
        if self.condition.is_set():
            # This will probably never be called, but better safe than sorry
            self.condition.set()
        self.events.safe_close()