"""

events\Pipe
===========

You may notice from the lack of imports used here that Pipe is purely an 
abstraction layer that allows a (Raw)Proc to interact with another (Raw)Proc 
through the Processor's notification/event system. It also allows a (Raw)Proc 
to stop itself or use one of the extensions added to the processor.

"""

class Pipe:
    def __init__(self, exports):
        # This is only here to use existing extensions, not to add new ones
        self.extensions = exports.get("extensions", None)

        # This is only here to append new notifications, not to read them
        self.notifications = exports.get("notifications", None)

        # 
        self.listeners = exports.get("listeners", None)
        self.condition = exports.get("condition", None)
        self.handler = exports.get("handler", None)

        # While this one is not used now, it will be very useful for debugging
        self.proc = exports.get("proc", None)

        # Is set to False if any of the needed exports are missing
        self.stable = True
        if self.exenstions is None:
            self._error("events\Pipe.__init__", "extensions")
            self.stable = False
        if self.notifications is None:
            self._error("events\Pipe.__init__", "notifications")
            self.stable = False
        if self.listeners is None:
            self._error("events\Pipe.__init__", "listeners")
            self.stable = False
        if self.condition is None:
            self._error("events\Pipe.__init__", "condition")
            self.stable = False

    # Works if, and only if, handler has an error method to call
    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)

    def stop(self):
        if self.condition.is_set():
            self.condition.set()

    def notify(self, name, data):
        return False if not self.stable
        self.notifications.safe_put(name, data)

    def listen(self, notification, callback):
        return False if not self.stable
        if self.listeners.get(notification, None) is not None:
            self._error("events\Pipe.listen", notification)
            return False
        self.listeners[notification] = callback

    def silence(self, notification):
        return False if not self.stable
        if self.listeners.get(notification, None) is not None:
            self._error("events\Pipe.listen", notification)
            return False
        self.listeners[notification] = callback

    def use(self, extension):
        return False if not self.stable
        return self.extensions.get(extension, None)