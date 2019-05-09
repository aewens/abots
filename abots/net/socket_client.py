"""

Socket Client
=============



"""

from abots.helpers import eprint, cast, jots, jsto, utc_now_timestamp

from struct import pack, unpack
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from ssl import wrap_socket
from threading import Thread, Event
from queue import Queue, Empty

class SocketClient(Thread):
    def __init__(self, host, port, buffer_size=4096, secure=False, 
        timeout=None):
        super().__init__()

        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.secure = secure
        self.timeout = timeout
        self.sock = socket(AF_INET, SOCK_STREAM)
        if self.secure:
            self.sock = wrap_socket(self.sock, **kwargs)

        self.connection = (self.host, self.port)
        self.running = True

        self.kill_switch = Event()
        self.ready = Event()
        self.stopped = Event()

        self._inbox = Queue()
        self._events = Queue()
        self._outbox = Queue()
        self.queues = dict()
        self.queues["inbox"] = self._inbox
        self.queues["outbox"] = self._outbox
        self.queues["events"] = self._events

    def _send_event(self, message):
        self._events.put(jots(message))
    
    def _prepare(self):
        self.sock.setblocking(False)
        self.sock.settimeout(1)
        try:
            self.sock.connect(self.connection)
        except OSError as e:
            return e
        return None
    
    def _obtain(self, queue, timeout=False):
        if timeout is False:
            timeout = self.timeout
        while True:
            try:
                if timeout is not None:
                    yield queue.get(timeout=timeout)
                else:
                    yield queue.get_nowait()
                queue.task_done()
            except Empty:
                break

    def _queue_thread(self, inbox, timeout):
        while not self.kill_switch.is_set():
            for message in self._obtain(inbox, timeout):
                self.send_message(message)

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

    def recv(self):
        return [letter for letter in self._obtain(self._outbox)]

    def send(self, message):
        self._inbox.put(message)

    def run(self):
        err = self._prepare()
        if err is not None:
            eprint(err)
            return err
        queue_args = self._inbox, self.timeout
        Thread(target=self._queue_thread, args=queue_args).start()
        print("Client ready!")
        self.ready.set()
        while self.running:
            message = self._get_message()
            if message is None:
                continue
            self._outbox.put(message)

    def stop(self, done=None):
        # print("Stopping client!")
        event = dict()
        event["name"] = "closing"
        event["data"] = dict()
        event["data"]["when"] = utc_now_timestamp()
        self._send_event(event)
        self.kill_switch.set()
        self.running = False
        self.sock.close()
        self.stopped.set()
        cast(done, "set")
        # print("Stopped client!")