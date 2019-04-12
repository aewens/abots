"""

events/SimpleProc & events/Proc
============================

This is designed to be used run by events/Processor to allow it to control 
whatever class is sent to it. The class will be spawned inside of events/Proxy 
so that operate better in a multiprocessing environment. As well, they will be 
provided an event/Shared for an event queue as well as a multiprocessing event 
to trigger the stop condition.

"""
from abots.events.pipe import Pipe
from abots.events import Every, Proxy, Shared
from abots.helpers import eprint

from multiprocessing import Process
from traceback import print_exc
from time import sleep

# The logic in Proc will have full control of how to process events
class Proc(Process):
    def __init__(self, name, logic, exports, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mainly used for SimpleProc
        self.name = name

        # This is an optional handler used for logging
        self.handler = exports.get("handler")

        # How long to wait for condition before timing out
        self.timeout = exports.get("timeout")

        # This is just a wrapper around multiprocessing.manager.Queue
        self.events = Shared(exports.get("events"))

        # This is used to indicate the stop condition for the process
        self.condition = exports.get("condition")

        # The notifications that the process will listen to
        self.listeners = exports.get("listeners")

        # Controls the events sent to/received by the Processor
        self.pipe = Pipe(exports)

        # Mainly used for setting self.logic in run, isolated from SimpleProc
        self._logic = logic

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
            self._error("event/Proc:call", method)
            return None
        # In case the method errors out, catch it here to prevent crashing
        try:
            return logic_method(*args, **kwargs)
        except Exception:
            status = print_exc()
            eprint(status)
            self._error("event/Proc:call!", status)
            return status

    # This is launched with `start` because of the Process inheritance
    def run(self):
        # All actions needed for logic can be leveraged through the pipe
        self.logic = self._logic(self.pipe)
        return self.call("start")

    # Cleans up the multiprocessing components
    def stop(self):
        # Stop is called here so it can choose what to do with the queue
        # Once it is done, it should set the condition so the events can close
        status = self.call("stop")
        # Wait until logic is done with the events, then close the queue
        self.condition.wait(timeout=self.timeout)
        self.events.safe_close()
        return status

# A simplified version where logic will only process the event given
class SimpleProc(Proc):
    def __init__(self, name, logic, exports, *args, **kwargs):
        # While timeout is still used, it is used only in `run` here
        super().__init__(name, logic, exports, *args, **kwargs)
        
        # Since logic can be a function in Proc, it is not initalized here
        self.logic = logic

        # By default, adds a listener from the proc's name
        self.pipe.listen(self.name)

    # This is launched with `start` because of the Process inheritance
    def run(self):
        while not self.condition.is_set():
            while not self.events.empty():
                # The pipe is sent so logic can use it to react to the event
                self.events.safe_apply(self.logic, self.pipe)
            # timeout is used here to add a delay in processing, if desired
            if self.timeout is not None:
                sleep(self.timeout)
        self.stop()
    
    # Cleans up the multiprocessing components
    def stop(self):
        # If the condition was not already set, do it now
        if self.condition.is_set():
            self.condition.set()
        self.events.safe_close()