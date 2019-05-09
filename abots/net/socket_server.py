"""

net/SocketServer
================

TODO:
* Add logging to broken pipe exceptions

"""

from abots.helpers import eprint, cast, sha256, utc_now_timestamp
from abots.helpers import jsto, jots

from threading import Thread, Event, Lock
from struct import pack, unpack
from select import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from time import time
from ssl import wrap_socket
from queue import Queue, Empty

class SocketServer(Thread):
    def __init__(self, host, port, listeners=5, buffer_size=4096, 
        secure=False, timeout=None, daemon=False):
        super().__init__()
        self.setDaemon(daemon)

        # The connection information for server, the clients will use this to 
        # connect to the server
        self.host = host
        self.port = port

        # The number of unaccepted connections that the system will allow 
        # before refusing new connections
        self.listeners = listeners

        # Size of buffer pulled by `receive_bytes` when not specified
        self.buffer_size = buffer_size

        # Determines if SSL wrapper is used
        self.secure = secure

        # Timeout set on queues
        self.timeout = timeout

        self._inbox = Queue()
        self._events = Queue()
        self._outbox = Queue()
        self.queues = dict()
        self.queues["inbox"] = self._inbox
        self.queues["outbox"] = self._outbox
        self.queues["events"] = self._events

        # Sets up the socket itself
        self.sock = socket(AF_INET, SOCK_STREAM)
        if self.secure:
            # Note: kwargs is used here to specify any SSL parameters desired
            self.sock = wrap_socket(self.sock, **kwargs)
        
        # List of all sockets involved (both client and server)
        self.sockets = list()
        self.clients = list()
        self.uuids = dict()

        # State variable for if the server is running or not. See `run`.
        self.kill_switch = Event()
        self.ready = Event()
        self.stopped = Event()

    def _send_event(self, message):
        self._events.put(jots(message))

    def _new_client(self, sock, address):
        sock.settimeout(60)
        client_host, client_port = address
        self.sockets.append(sock)

        client_kill = Event()
        client_uuid = sha256()
        self.uuids[client_uuid] = dict()
        self.uuids[client_uuid]["sock"] = sock
        self.uuids[client_uuid]["kill"] = client_kill

        event = dict()
        event["name"] = "new_client"
        event["data"] = dict()
        event["data"]["host"] = client_host
        event["data"]["port"] = client_port
        event["data"]["uuid"] = client_uuid
        self._send_event(event)

        client_args = sock, client_kill, client_uuid
        client_thread = Thread(target=self._client_thread, args=client_args)
        self.clients.append(client_thread)
        client_thread.start()

    # Logic for the client socket running in its own thread
    def _client_thread(self, sock, kill_switch, uuid):
        while not kill_switch.is_set():
            try:
                message = self.get_message(uuid)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                eprint(e)
                break
            if message is None:
                continue
            # Send message and uuid of sender to outbox queue
            letter = uuid, message
            self._outbox.put(letter)

    def _queue_thread(self, inbox, timeout):
        while not self.kill_switch.is_set():
            for letter in self._obtain(inbox, timeout):
                if len(letter) != 2:
                    continue
                uuid, message = letter
                if uuid == "cast":
                    self.broadcast_message(uuid, message)
                else:
                    self.send_message(uuid, message)

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

    # Prepares socket server before starting it
    def _prepare(self):
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.host, self.port))
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            # This usually means that the port is already in use
            return e
        self.sock.setblocking(0)
        self.sock.settimeout(0)
        self.sock.listen(self.listeners)
        self.sockets.append(self.sock)
        return None

    def _sock_from_uuid(self, uuid):
        return self.uuids.get(uuid, dict()).get("sock", None)

    def _package_message(self, message, *args):
        if len(args) > 0:
            formatted = message.format(*args)
        else:
            formatted = message
        packaged = pack(">I", len(formatted)) + formatted.encode()
        return packaged

    # Closes a connected socket and removes it from the sockets list
    def close_sock(self, uuid):
        event = dict()
        event["name"] = "close_client"
        event["data"] = dict()
        event["data"]["uuid"] = uuid
        self._send_event(event)
        if uuid in list(self.uuids):
            sock = self.uuids[uuid]["sock"]
            kill = self.uuids[uuid]["kill"]
            kill.set()
            del self.uuids[uuid]
            self.sockets.remove(sock)
            sock.close()

    # Receives specified number of bytes from a socket
    # sock - one of the sockets in sockets
    # get_bytes - number of bytes to receive from socket
    # decode - flag if the returned data is binary-to-string decoded
    def receive_bytes(self, sock, get_bytes, decode=True):
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
                packet = sock.recv(bufsize)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                return None
            data = data + packet
        return data.decode() if decode else data

    # Get message from socket
    def get_message(self, uuid):
        sock = self._sock_from_uuid(uuid)
        if sock is None:
            return None
        raw_message_size = self.receive_bytes(sock, 4, False)
        if raw_message_size is None or len(raw_message_size) != 4:
            return None
        message_size = unpack(">I", raw_message_size)[0]
        return self.receive_bytes(sock, message_size)

    # Packages a message and sends it to socket
    def send_message(self, uuid, message, *args):
        sock = self._sock_from_uuid(uuid)
        if sock is None:
            return None
        formatted = self._package_message(message)
        try:
            sock.send(formatted)
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            return

    # Like send_message, but sends to all sockets but the server and the sender
    def broadcast_message(self, client_uuid, message, *args):
        for uuid in list(self.uuids):
            if uuid != client_uuid:
                self.send_message(uuid, message, *args)

    def recv(self):
        return [letter for letter in self._obtain(self._outbox)]

    def send(self, uuid, message):
        letter = uuid, message
        self._inbox.put(letter)

    # The function for running the socket server logic loop
    def run(self):
        err = self._prepare()
        if err is not None:
            eprint(err)
            return err
        queue_args = self._inbox, self.timeout
        Thread(target=self._queue_thread, args=queue_args).start()
        # print("Server ready!")
        self.ready.set()
        while not self.kill_switch.is_set():
            try:
                # Accept new socket client
                client_sock, client_address = self.sock.accept()
                # print(client_address)
                self._new_client(client_sock, client_address)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                continue

    # Stop the socket server
    def stop(self, done=None, join=False):
        event = dict()
        event["name"] = "closing"
        event["data"] = dict()
        event["data"]["when"] = utc_now_timestamp()
        self._send_event(event)
        for uuid in list(self.uuids):
            self.close_sock(uuid)
        self.kill_switch.set()
        self.sock.close()
        if join:
            for client in self.clients:
                client.join(self.timeout)
        self.stopped.set()
        cast(done, "set")