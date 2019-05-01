"""

Socket Server Handlers
======================



"""

from abots.helpers import cast

from time import sleep
from struct import pack, unpack

class SocketServerHandler:
    def __init__(self, server):
        self.server = server
        self.imports = dict()

    def load(self, imports):
        self.imports = imports

    def pre_process(self):
        kill_switch = self.imports.get("kill_switch", None)
        if kill_switch is None:
            return False
        if kill_switch.is_set():
            self.server.stop()
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

    # Tells all clients that a node joined the socket server
    def open_client(self, address, port):
        pass

    # Informs the other clients a client left and closes that client's socket
    def close_client(self, sock):
        pass

    def close(self):
        pass

    # Format a message before sending to client(s)
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

    def message(self, sock, message):
        print(f"DEBUG: {message}")
        if message == "PING":
            sleep(1)
            self.server.send_message(sock, "PONG")