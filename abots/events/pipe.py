"""

events/Pipe
===========

This is purely an abstraction layer that allows a (Simple)Proc to interact with 
another (Simple)Proc through the Processor's notification/event system. It also 
allows a (Simple)Proc to stop itself or use one of the extensions added to the 
processor.

"""

from abots.events import Shared

class Pipe:
    def __init__(self, exports):
        # This is only here to use existing extensions, not to add new ones
        self.extensions = exports.get("extensions", None)

        # This is only here to append new notifications, not to read them
        self.notifications = Shared(exports.get("notifications", None))

        # This is used to append new listeners to subscribe to
        self.listeners = exports.get("listeners", None)

        # This is used to stop the proc the pipe is connected to
        self.condition = exports.get("condition", None)

        # This is used to stop the proc the pipe is connected to
        self.events = exports.get("events", None)

        # This is an optional handler used for logging
        self.handler = exports.get("handler", None)

        # While this one is not used now, it will be very useful for debugging
        self.proc = exports.get("proc", None)

        # Is set to False if any of the needed exports are missing
        self.stable = True
        if self.extensions is None:
            self._error("events/Pipe.__init__", "extensions")
            self.stable = False
        if self.notifications is None:
            self._error("events/Pipe.__init__", "notifications")
            self.stable = False
        if self.listeners is None:
            self._error("events/Pipe.__init__", "listeners")
            self.stable = False
        if self.condition is None:
            self._error("events/Pipe.__init__", "condition")
            self.stable = False
        if self.events is None:
            self._error("events/Pipe.__init__", "events")
            self.stable = False

    # Works if, and only if, handler has an error method to call
    def _error(self, name, data):
        if self.handler is None:
            return None
        elif getattr(self.handler, "error", None):
            return None
        self.handler.error(name, data)

    # Informs the associated proc to stop running
    def stop(self):
        if self.condition.is_set():
            self.condition.set()

    # Dispatches a new notification to the processor
    def notify(self, name, data):
        if not self.stable:
            return False
        print(f"Notifying {name}: {data}")
        return self.notifications.safe_put((name, data))

    # Informs the pipe to add a new notification listener
    def listen(self, notification):
        if not self.stable:
            return False
        if notification in self.listeners:
            self._error("events/Pipe.listen", notification)
            return False
        self.listeners.append(notification)

    # Informs the pipe to remove a new notification listener
    def silence(self, notification):
        if not self.stable:
            return False
        if notification in self.listeners:
            self._error("events/Pipe.listen", notification)
            return False
        self.listeners.remove(notification)

    # Utilizes one of the extensions loaded by the processor
    def use(self, extension):
        if not self.stable:
            return False
        return self.extensions.get(extension, None)