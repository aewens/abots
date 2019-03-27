from abots.events.pipe import Pipe
from abots.events.module import Module

from time import time
from multiprocessing import Process, Manager
# Queue, JoinableQueue

class Dispatcher:
    def __init__(self, handler=None):
        self.modules = dict()
        self.handler = handler

        manager = Manager()
        self.extenstions = manager.dict()
        self.notifications = manager.dict()

    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)

    def _is_module_init(self, module, destroy=False):
        if not proc:
            return False
        instance = getattr(module, "instance", None)
        return not instance if destroy else instance

    def _start(self, mod, handler=None, *args, **kwargs):
        module = self.modules.get(mod, None)
        if self._is_module_init(module):
            self._error("_start", mod)
            return None
        events = None
        kwargs = dict()
        if handler is not None:
            kwargs["handler"] = handler
        events = Pipe(module, self.extensions, self.notifications, **kwargs)
        module.instance = module.logic(events)
        if getattr(module.instance, "create", None) is not None:
            return module.instance.create(*args, **kwargs)

    def start(self, module):
        pass

    def extend(self, name, logic):
        self.extensions[name] = logic

    def register(self, module, logic):
        if self.modules.get(module, None) is None:
            self._error("register", module)
            return None
        self.modules[name] = Module(logic)