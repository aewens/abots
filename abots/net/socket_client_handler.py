"""

Socket Client Handlers
======================



"""

from abots.helpers import cast

from time import sleep
from struct import pack, unpack

class SocketClientHandler:
    def __init__(self, client):
        self.client = client
        self.imports = dict()

    def load(self, imports):
        self.imports = imports

    def pre_process(self):
        kill_switch = self.imports.get("kill_switch", None)
        if kill_switch is None:
            return False
        if kill_switch.is_set():
            self.client.stop()
            return True
        return False

    def post_process(self):
        kill_switch = self.imports.get("kill_switch", None)
        mailbox = self.imports.get("mailbox", None)
        # pid = self.imports.get("pid", None)
        # ledger = self.imports.get("ledger", None)
        if kill_switch is None or mailbox is None:
            return
        while not kill_switch.is_set():
            while not mailbox.empty():
                message = mailbox.get()
                print("POST", message)

    # Prepends message size code along with replacing variables in message
    def format(self, message, *args):
        formatted = None
        if len(args) > 0:
            formatted = message.format(*args)
        else:
            formatted = message
        
        # Puts message size at the front of the message
        prefixed = pack(">I", len(formatted)) + formatted.encode()
        return prefixed

    def initialize(self):
        self.client.send_message("PING")

    def message(self, message):
        print(f"DEBUG: {message}")
        if message == "PONG":
            sleep(1)
            self.client.send_message("PING")