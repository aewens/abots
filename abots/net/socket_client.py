"""

Socket Client
=============



"""

from abots.helpers import eprint, cast

from struct import pack, unpack
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from ssl import wrap_socket

class SocketClient():
    def __init__(self, host, port, handler, buffer_size=4096, secure=False, 
        *args, **kwargs):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.secure = secure
        self.handler = handler(self, *args, **kwargs)
        self.sock = socket(AF_INET, SOCK_STREAM)
        if self.secure:
            self.sock = wrap_socket(self.sock, **kwargs)

        self.connection = (self.host, self.port)
        self.running = True

    def _recv_bytes(self, get_bytes, decode=True):
        data = "".encode()
        attempts = 0
        while len(data) < get_bytes:
            # Automatically break loop to prevent infinite loop
            # Allow at least twice the needed iterations to occur exiting loop
            if attempts > 2 * (get_bytes / self.buffer_size):
                break
            else:
                attempts = attempts + 1
            bufsize = get_bytes - len(data)

            # Force bufsize to cap out at buffer_size
            if bufsize > self.buffer_size:
                bufsize = self.buffer_size
            try:
                packet = self.sock.recv(bufsize)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                return None
            data = data + packet
        return data.decode() if decode else data

    def _package_message(self, message, *args):
        if len(args) > 0:
            formatted = message.format(*args)
        else:
            formatted = message
        packaged = pack(">I", len(formatted)) + formatted.encode()
        return packaged

    def _get_message_size(self):
        raw_message_size = self._recv_bytes(4, False)
        if not raw_message_size:
            return None
        message_size = unpack(">I", raw_message_size)[0]
        return message_size

    def _get_message(self):
        message_size = self._get_message_size()
        if message_size is None:
            return None
        try:
            return self._recv_bytes(message_size)
        except OSError:
            return None

    def send_message(self, message, *args):
        packaged = self._package_message(message, *args)
        try:
            self.sock.send(packaged)
        except OSError:
            self.stop()

    def _prepare(self):
        self.sock.setblocking(False)
        self.sock.settimeout(1)
        try:
            self.sock.connect(self.connection)
        except OSError as e:
            return e
        return None

    def from_actor(self, imports):
        cast(self.handler, "load", imports)

    def start(self):
        err = self._prepare()
        if err is not None:
            eprint(err)
            return err
        # print("Ready!")
        cast(self.handler, "initialize")
        while self.running:
            cast(self.handler, "pre_process")
            message = self._get_message()
            if message is None:
                continue
            cast(self.handler, "message", message)

            cast(self.handler, "post_process")

    def stop(self, done=None):
        # print("Stopping client!")
        self.running = False
        self.sock.close()
        cast(done, "set")
        # print("Stopped client!")