"""

events/Processor
================

This is where all of the magic happens. The processor will allow you to spin up 
a bunch of processes and allow them to communicate over a shared event queue. 
It does all of this using a handful of multiprocessing abstractions included in 
the "events" sub-module.

"""

from abots.events.proc import Proc, SimpleProc
from abots.events.shared import Shared
from abots.events import Every, Proxy
from abots.helpers import ctos

from time import sleep
from multiprocessing import Process, Manager

class Processor(Process):
    def __init__(self, handler=None, timeout=None):
        super().__init__()

        # This provides the means to create shareable dictionaries
        self.manager = Manager()

        # This is an optional handler used for logging
        self.handler = handler
        
        # Dictates whether the notifications need a timeout for get/put actions
        self.timeout = timeout

        # All of the procs handled by the processor
        self.procs = dict()

        # All of the procs that are actively running
        self.active = dict()

        # Any extensions that have been loaded into the processor
        self.extensions = self.manager.dict()

        # The shared event queue for notifications for the procs
        self.notifications = Shared(self.manager.Queue())

        # The stop condition to halt the processor and all of its processes
        self.condition = self.manager.Event()

        # Used later to export settings inherited by the procs
        self.exports = self._export()

    # Works if, and only if, handler has an error method to call
    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)
        return True

    # Creates a dictionary of the shared settings to pass to procs
    def _export(self):
        exports = dict()
        exports["notifications"] = self.notifications.queue
        exports["extensions"] = self.extensions
        if self.handler is not None:
            exports["handler"] = self.handler
        return exports

    # Determine if a process exists, is formatted correctly, and active
    def _check_process(self, name):
        proc = self.procs.get(name, None)
        if proc is None:
            self._error("events/Processor._check_process", name)
            return None, None
        active = self.active.get(name, None)
        return proc, active

    # Wrapper for calling actions on all procs
    def _all(self, action_name, **kwargs):
        statuses = dict()
        action = getattr(self, action_name, None)
        if action is None:
            self._error("events/Processor._all", action_name)
            return None
        for proc_name in self.procs.keys():
            proc_kwargs = kwargs.get(proc_name, dict())
            # Save the status of the action for any error reporting
            statuses[proc_name] = action(proc_name, **proc_kwargs)
        return statuses

    # Add the extension through a Proxy to work across procs
    def extend(self, name, logic, *args, **kwargs):
        self.extensions[name] = Proxy(logic).make(*args, **kwargs)

    # The loop that handles distributing notifications to their procs
    def run(self):
        while not self.condition.is_set():
            while not self.notifications.empty():
                notification = self.notifications.safe_get()
                print("Notification:", notification)
                print(self.active)
                # We do not care about the proc's name here, only values needed
                for name, info in self.active.items():
                    print(info)
                    # The proc has been stopped, tell processor to spin it down
                    if info["condition"].is_set():
                        self.spindown()
                        continue
                    for event_name in info["listeners"]:
                        # name, data = notification
                        if event_name != notification[0]:
                            continue
                        Shared(info["events"]).safe_put(notification, self.timeout)

    # Clean up everything that needs to be stopped 
    def stop(self):
        # Determine the max time procs will take to spin down
        timeout = 0 if self.timeout is None else self.timeout
        wait = timeout * len(self.procs)
        # Spin down all of the procs, then sets the stop condition
        self.spindown_all()
        # Give procs enough time to spin down
        self.condition.wait(wait)
        # Close the notification loop, return all of the entries not processed
        return Shared(self.notifications).safe_close()

    # Informs the processor of the proc, does not start it
    def register(self, proc, name=None, simple=False):
        if name is None:
            # Class-to-String helper function, extracts name of class
            name = ctos(proc)
        if name in self.procs:
            self._error("events/Processor.register", name)
            return None
        proc_info = dict()
        proc_info["logic"] = proc
        proc_info["simple"] = simple
        self.procs[name] = proc_info
        return True

    # Starts the proc and loads into into self.active
    def spinup(self, name, timeout=None, *args, **kwargs):
        print(f"Spinning up {name}")
        proc, active = self._check_process(name)
        if not proc or active:
            return None
        simple = proc.get("simple", False)
        logic = proc.get("logic", None)
        if logic is None:
            self._error("events/Processor.start", name)
            return None
        # These are defined here so that proc objects do not need to be shared
        listeners = self.manager.list()
        condition = self.manager.Event()
        events = self.manager.Queue()

        exports = self.exports.copy()
        exports["proc"] = name
        exports["listeners"] = listeners
        exports["condition"] = condition
        exports["events"] = events
        if timeout is not None:
            exports["timeout"] = timeout
        proxy_args = (name, logic, exports, *args)
        if simple:
            # procedure = Proxy(SimpleProc).make(*proxy_args, **kwargs)
            procedure = SimpleProc(*proxy_args, **kwargs)
        else:
            # procedure = Proxy(Proc).make(*proxy_args, **kwargs)
            procedure = Proc(*proxy_args, **kwargs)
        procedure.start()
        active_info = dict()
        active_info["listeners"] = listeners
        active_info["condition"] = condition
        active_info["events"] = events
        print(active_info)
        self.active[name] = active_info
        print(self.active)
        return True

    # Stops the proc and removes it from self.active
    def spindown(self, name):
        print(f"Spinning down {name}")
        proc, active = self._check_process(name)
        if not proc or not active:
            return None
        condition = active.get("condition", None)
        if condition is None:
            self._error("events/Processor.spindown", active)
        condition.set()
        del self.active[name]
        return True

    # Start all of the procs
    def spinup_all(self, **kwargs):
        return self._all("spinup", **kwargs)

    # Stop all of the procs
    def spindown_all(self, **kwargs):
        self.condition.set()
        return self._all("spindown", **kwargs)