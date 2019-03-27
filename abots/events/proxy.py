"""

events\Proxy
============

This is used to act as a proxy for sending classes / objects between other 
processes, ideally without running into race conditions.

"""

from abots.helpers import ctos

from re import compile as regex
from multiprocessing.managers import BaseManager

class ProxyManager(BaseManager):
    pass

class Proxy:
    def __init__(self, modules):
        self.modules = modules if type(modules) is list else [modules]
        self._create_proxy_manager()

    # Gets the module as-is, which should be a class to be called
    def get(self, module):
        return getattr(self._proxy_manager, module, None)

    # Returns the module as an object using the provided arguments
    def obj(self, module, *args, **kwargs):
        return self.get(module)(*args, **kwargs)

    # Lists all of the modules stored in the proxy manager
    def gather(self):
        return [pm for pm in dir(self._proxy_manager) if pm[0].isupper()]

    # If there is only one module, it makes it into a proxy object
    def make(self, *args, **kwargs):
        gather = self.gather
        if len(gather) != 1:
            return None
        return self.obj(gather[0], *args, **kwargs)

    def _create_proxy_manager(self):
        for module in self.modules:
            module_name = ctos(module)
            ProxyManager.register(module_name, module)
        proxy_manager = ProxyManager()
        proxy_manager.start()
        self._proxy_manager = proxy_manager