"""

events/Proxy
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
    def __init__(self, module):
        self.module = module
        self.name = ctos(self.module)
        self._create_proxy_manager()

    # Gets the module as-is, which should be a class to be called
    def get(self):
        return getattr(self._proxy_manager, self.name, None)

    # Makes the proxy module into a proxy object
    def make(self, *args, **kwargs):
        return self.get()(*args, **kwargs)

    def _create_proxy_manager(self):
        ProxyManager.register(self.name, self.module)
        proxy_manager = ProxyManager()
        proxy_manager.start()
        self._proxy_manager = proxy_manager