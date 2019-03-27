from abots.events.proc import Proc
from abots.events.shared import Shared
from abots.events import Every, Proxy
from abots.helpers import ctos

from time import sleep
from multiprocessing import Event, Process, Manager

class Processor(Process):
    def __init__(self, handler=None, timeout=None):
        super().__init__(self)
        manager = Manager()
        self.handler = handler
        self.timeout = timeout
        self.procs = manager.dict()
        self.active = manager.dict()
        self.extenstions = manager.dict()
        self.notifications = Shared()
        self.condition = Event()
        self.exports = self._export()

    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)
        return True

    def _export(self):
        exports = dict()
        exports["notifications"] = self.notifications
        exports["extensions"] = self.extenstions
        if self.handler is not None:
            exports["handler"] = self.handler
        return exports

    def _check_process(self, name):
        proc = self.procs.get(name, None)
        if proc is None or type(proc) is not dict:
            self._error("events\Processor._check_process", name)
            return None, None
        active = self.active.get(name, None)
        return proc, active

    def _all(self, action_name, **kwargs):
        statuses = dict()
        action = getattr(self, action_name, None)
        if action is None:
            self._error("events\Processor._all", action_name)
            return None
        for proc in self.procs:
            proc_kwargs = proc_kwargs = kwargs.get(proc, dict())
            statuses[proc] = action(proc, **proc_kwargs)
        return statuses

    def run(self):
        while not self.condition.is_set():
            while not self.notifications.empty():
                notification = self.notifications.safe_get()
                name, data = notification
                for proc_name, proc in self.active.items():
                    if proc.condition.is_set():
                        self.spindown()
                        continue
                    for event_name in proc.listeners:
                        if name == event_name:
                            proc.events.safe_put(notification, self.timeout)
    
    def stop(self):
        self.spindown_all()
        self.notifications.safe_close()

    def extend(self, name, logic, *args, **kwargs):
        self.extensions[name] = Proxy(logic).make(*args, **kwargs)

    def register(self, proc, name=None, simple=False):
        if name is None:
            name = ctos(proc)
        if name in self.procs:
            self._error("events\Processor.register", name)
            return None
        self.procs[name] = dict()
        self.procs[name]["logic"] = proc
        self.procs[name]["simple"] = simple
        return True

    def spinup(self, name, timeout=None, *args, **kwargs):
        proc, active = self._check_process(self, name)
        if not proc or active:
            return None
        simple = proc.get("simple", False)
        logic = proc.get("logic", None)
        if logic is None:
            self._error("events\Processor.start", name)
            return None

        exports = self.exports.copy()
        exports["proc"] = name
        if timeout is not None:
            exports["timeout"] = timeout

        proxy_args = (logic, exports, *args, **kwargs)
        if simple:
            procedure = Proxy(SimpleProc).make(*proxy_args)
        else:
            procedure = Proxy(Proc).make(*proxy_args)
        procedure.start()
        self.active[name] = procedure
        return True

    def spindown(self, name):
        proc, active = self._check_process(self, name)
        if not proc or not active:
            return None
        active.stop()
        del self.active[name]
        return True

    def spinup_all(self, **kwargs):
        return self._all("spinup")

    def spindown_all(self, **kwargs):
        statuses = self._all("spindown")
        self.condition.set()
        return statuses