"""

Socket Server Handlers
======================



"""

from time import sleep
from struct import pack, unpack

class SocketClientHandler:
    def __init__(self, client):
        self.client = client

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