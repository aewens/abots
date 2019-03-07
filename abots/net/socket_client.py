from struct import pack, unpack
from multiprocessing import Process, Queue, JoinableQueue
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

class SocketClient(Process):
    def __init__(self, host, port, buffer_size=4096, end_of_line="\r\n", 
        inbox=JoinableQueue(), outbox=Queue(), handler=lambda x: x):
        Process.__init__(self)

        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.end_of_line = end_of_line
        self.handler = handler
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.connection = (self.host, self.port)
        self.running = True
        self.inbox = inbox
        self.outbox = outbox
        self.error = None

    def _recv_bytes(self, get_bytes, decode=True):
        data = "".encode()
        eol = self.end_of_line.encode()
        while len(data) < get_bytes:
            bufsize = get_bytes - len(data)
            if bufsize > self.buffer_size:
                bufsize = self.buffer_size
            try:
                packet = self.sock.recv(bufsize)
            except OSError:
                return None
            length = len(data) + len(packet)
            checker = packet if length < get_bytes else packet[:-2]
            if eol in checker:
                packet = packet.split(eol)[0] + eol
                return data + packet
            data = data + packet
        return data.decode() if decode else data

    def _package_message(self, message, *args):
        formatted = None
        if len(args) > 0:
            formatted = message.format(*args) + self.end_of_line
        else:
            formatted = message + self.end_of_line
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
            return self._recv_bytes(message_size).strip(self.end_of_line)
        except OSError:
            return None

    def _send_message(self, message, *args):
        packaged = self._package_message(message, *args)
        try:
            self.sock.send(packaged)
        except OSError:
            self.stop()

    def _process_inbox(self):
        while not self.inbox.empty():
            message, args = self.inbox.get()
            self._send_message(message, *args)
            self.inbox.task_done()

    def _prepare(self):
        self.sock.setblocking(False)
        self.sock.settimeout(1)
        try:
            self.sock.connect(self.connection)
        except OSError as e:
            return e
        return None

    def send(self, message, *args):
        self.inbox.put((message, args))

    def results(self):
        messages = list()
        while not self.outbox.empty():
            messages.append(self.outbox.get())
        return messages

    def run(self):
        err = self._prepare()
        if err is not None:
            print(err)
            return err
        print("Ready!")
        while self.running:
            data = self._get_message()
            if data is not None:
                self.outbox.put(self.handler(data))
            self._process_inbox()

    def stop(self):
        self.running = False
        self.sock.close()
        self.terminate()