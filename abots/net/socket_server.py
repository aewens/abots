"""

net\SocketServer
================

The intent behind this script is to provide a simple interface to start up a 
TCP socket server in the background, run each of the clients in their own 
thread, provide a simple system to handle server events, and provide simple 
functions to send/receive messages from the server.

"""

from abots.net.socket_server_handler import SocketServerHandler as handler

from threading import Thread
from struct import pack, unpack
from select import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from multiprocessing import Process, Queue, JoinableQueue
from time import time
from ssl import wrap_socket

# Inherits Process so that server can be run as a daemon
class SocketServer(Process):
    # There are many parameters here, but that is so that any constant used can 
    # be easily tweaked and not remain hard-coded without an easy way to change 
    def __init__(self, host, port, listeners=5, buffer_size=4096, secure=False, 
        timeout=0.02, max_message_size=-1, end_of_line="\r\n", heartbeat=60, 
        inbox=JoinableQueue(), outbox=Queue(), handler=handler, **kwargs):
        super().__init__(self)

        # The connection information for server, the clients will use this to 
        # connect to the server
        self.host = host
        self.port = port

        # The number of unaccepted connections that the system will allow 
        # before refusing new connections
        self.listeners = listeners

        # Size of buffer pulled by `receive_bytes` when not specified
        self.buffer_size = buffer_size

        # Timeout for the socket server, in term of seconds
        self.timeout = timeout

        # If max_message_size is -1, it allows any message size
        self.max_message_size = max_message_size

        # Which character(s) will terminate a message
        self.end_of_line = end_of_line

        # Determines if SSL wrapper is used
        self.secure = secure

        # How often a heartbeat will be sent to a client
        self.heartbeat = heartbeat

        # Queues used for sending messages and receiving results using `send` 
        # and `results`
        self.inbox = inbox
        self.outbox = outbox

        # An object that determines how the server reacts to events, will use 
        # net\SocketServerHandler if none are specified. Use it as a model for 
        # how other handlers should look / work.
        self.handler = handler(self)

        # Sets up the socket itself
        self.sock = socket(AF_INET, SOCK_STREAM)
        if self.secure:
            # Note: kwargs is used here to specify any SSL parameters desired
            self.sock = wrap_socket(self.sock, **kwargs)

        # Will later be set to the file descriptor of the socket on the server
        # See `_prepare`
        self.sock_fd = -1
        
        # Will later be set to the alias used for the socket on the server
        # See `_prepare`
        self.sock_alias = None

        # List of all sockets involved (both client and server)
        self.sockets = list()

        # Maps metadata about the clients
        self.clients = dict()

        # State variable for if the server is running or not. See `run`.
        self.running = True

    # Sends all messages queued in inbox
    def _process_inbox(self):
        while not self.inbox.empty():
            # In the format" mode, message, args
            data = self.inbox.get()
            mode = data[0]
            # Send to one socket
            if mode == self.handler.send_verb:
                client, message, args = data[1:]
                self.send_message(message, *args)
            # Broadcast to sockets
            elif mode == self.handler.broadcast_verb:
                message, args = data[1:]
                self.broadcast_message(self.sock, message, *args)
            self.inbox.task_done()

    # Logic for the client socket running in its own thread
    def _client_thread(self, sock, alias):
        last = time()
        client = self.clients[alias]
        while self.running:
            now = time()
            # Run heartbeat after defined time elapses
            # This will probably drift somewhat, but this is fine here
            if now - last >= self.heartbeat:
                # If the client missed last heartbeat, close client
                if not client["alive"]:
                    self.handler.close_client(alias)
                    break
                # The handler must set this to True, this is how a missed 
                # heartbeat is checked later on
                client["alive"] = False
                last = now
                self.handler.send_heartbeat(alias)
            try:
                message = self.handler.get_message(sock)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                # In this case, the socket most likely died before the 
                # heartbeat caught it
                self.handler.close_client(alias)
                break
            if message is None:
                continue
            # Each message returns a status code, exactly which code is 
            # determined by the handler
            status = self.handler.message(sock, message)
            # Send status and message received to the outbox queue
            self.outbox.put((status, message))

    # Prepares socket server before starting it
    def _prepare(self):
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.host, self.port))
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            # This usually means that the port is already in use
            return e
        self.sock.settimeout(self.timeout)
        self.sock.listen(self.listeners)

        # Gets the file descriptor of the socket, which is a fallback for a 
        # unique identifier for the sockets when an alias does not work
        self.sock_fd = self.sock.fileno()
        sock_address = self.sock.getsockname()
        sock_host, sock_port = sock_address
        
        # This may change later, but for now aliases start at @0 and continue 
        # on from there numerically
        self.sock_alias = "@{}".format(len(self.sockets))
        self.sockets.append(self.sock)

        # Set metadata about the socket server, the fd and alias are both set 
        # here to make obtaining the other metadata possible with less lookups
        self.clients[self.sock_fd] = dict()
        self.clients[self.sock_fd]["fd"] = self.sock_fd
        self.clients[self.sock_fd]["host"] = sock_host
        self.clients[self.sock_fd]["port"] = sock_port
        self.clients[self.sock_fd]["sock"] = self.sock
        self.clients[self.sock_fd]["alias"] = self.sock_alias

        # Here the alias is just a pointer to the same data, or at least acts 
        # like a pointer given how Python handles dictionaries referencing the 
        # same data
        self.clients[self.sock_alias] = self.clients[self.sock_fd]
        return None

    # Closes a connected socket and removes it from the server metadata
    def close_sock(self, alias):
        client = self.clients.get(alias, None)
        if client is None:
            return None
        sock = client["sock"]
        fd = client["fd"]
        self.sockets.remove(sock)
        if fd is not None:
            # While the alias is a pointer, you need to delete both 
            # individually to truly remove the socket from `clients`
            del self.clients[fd]
            del self.clients[alias]
        sock.close()

    # Receives specified number of bytes from a socket
    # sock - one of the sockets in sockets
    # get_bytes - number of bytes to receive from socket
    # decode - flag if the returned data is binary-to-string decoded
    def receive_bytes(self, sock, get_bytes, decode=True):
        data = "".encode()
        eol = self.end_of_line.encode()
        # Auto-fail if requested bytes is greater than allowed by server
        if self.max_message_size > 0 and get_bytes > self.max_message_size:
            return None
        attempts = 0
        while len(data) < get_bytes:
            # Automatically break loop to prevent infinite loop
            if self.max_message_size > 0:
                if attempts > self.max_message_size / self.buffer_size:
                    break
                else:
                    attempts = attempts + 1
            else:
                # With max_message_size not set, allow at least twice the 
                # needed iterations to occur before breaking loop
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
            length = len(data) + len(packet)
            checker = packet if length < get_bytes else packet[:-2]

            # Automatically stop reading message if EOL character sent
            if eol in checker:
                packet = packet.split(eol)[0] + eol
                return data + packet
            data = data + packet
        return data.decode() if decode else data

    # Packages a message and sends it to socket
    def send_message(self, sock, message, *args):
        formatted = self.handler.format_message(message, *args)
        try:
            sock.send(formatted)
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            alias = self.get_client_alias_by_sock(sock)
            if alias is not None:
                self.close_sock(alias)

    # Like send_message, but sends to all sockets but the server and the sender
    def broadcast_message(self, client_sock, client_message, *args):
        for sock in self.sockets:
            not_server = sock != self.sock
            not_client = sock != client_sock
            if not_server and not_client:
                self.send_message(sock, client_message, *args)

    # Obtains file descriptor of the socket
    def get_client_fd(self, client_sock):
        try:
            # First, try the easy route of just pulling it directly
            return client_sock.fileno()
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            # Otherwise, the socket is probably dead and we can try finding it 
            # using brute-force. This sometimes works
            for fd, sock in self.sockets:
                if sock != client_sock:
                    continue
                return fd
            # If the brute-force option does not work, I cannot think of a good 
            # way to get the fd aside from passing it along everywhere that 
            # sock is also used, which would be extremely tedios. However, if 
            # you have the alias you can skip this entirely and just pull the 
            # fd from `clients` using the alias
            return None

    # I realize the function name here is long, but for the few times I use 
    # this it makes it clear exactly what magic is going on
    def get_client_alias_by_sock(self, client_sock):
        client_fd = self.get_client_fd(client_sock)
        if client_fd is None:
            return None
        return self.clients.get(client_fd, dict()).get("alias", None)

    # Externally called function to send a message to a client
    def send(self, client, message, *args):
        # This queue will be read by `_process_inbox` during the next loop
        self.inbox.put((self.handler.send_verb, client, message, args))

    # Externally called function to broadcast a message to all clients
    def broadcast(self, message, *args):
        # This queue will be read by `_process_inbox` during the next loop
        self.inbox.put((self.handler.broadcast_verb, message, args))

    # Externally called function to iterates over the outbox queue and returns 
    # them as a list in FIFO order
    def results(self, remove_status=False):
        messages = list()
        while not self.outbox.empty():
            result = self.outbox.get()
            # For when you do not care about the status codes
            if remove_status:
                status, message = result
                messages.append(message)
            else:
                messages.append(result)
        return messages

    # The Process function for running the socket server logic loop
    def run(self):
        err = self._prepare()
        if err is not None:
            print(err)
            return err
        # print("Server ready!")
        while self.running:
            try:
                # Accept new socket client
                client_sock, client_address = self.sock.accept()
                client_sock.settimeout(60)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                continue

            # Collect the metadata of the client socket
            client_name = "{}:{}".format(*client_address)
            client_host, client_port = client_address
            client_fd = client_sock.fileno()
            client_alias = "@{}".format(len(self.sockets))

            # Define metadata for client
            self.sockets.append(client_sock)
            self.clients[client_fd] = dict()
            self.clients[client_fd]["fd"] = client_fd
            self.clients[client_fd]["host"] = client_host
            self.clients[client_fd]["port"] = client_port
            self.clients[client_fd]["sock"] = client_sock
            self.clients[client_fd]["alias"] = client_alias
            self.clients[client_fd]["alive"] = True

            # The alias is just a key that points to the same metadata
            self.clients[client_alias] = self.clients[client_fd]

            # Have handler process new client event
            status = self.handler.open_client(client_alias)

            # Send status and message received to the outbox queue
            self.outbox.put((status, message))

            # Spawn new thread for client
            args = (client_sock, client_alias)
            Thread(target=self._client_thread, args=args).start()
            
            # Process messages waiting in inbox queue
            # This is done at the end in case for some weird reason a message 
            # is sent to the new client in the middle of processing this data 
            # it eliminates the chance of a race condition.
            self._process_inbox()

    # Stop the socket server
    def stop(self):
        self.handler.close_server()
        self.running = False
        self.sock.close()