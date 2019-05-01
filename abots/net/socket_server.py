"""

net/SocketServer
================


"""

from abots.events import Envelope
from abots.helpers import eprint, cast

from threading import Thread, Event
from struct import pack, unpack
from select import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from time import time
from ssl import wrap_socket

class SocketServer:
    def __init__(self, host, port, handler, listeners=5, buffer_size=4096, 
        secure=False, *args, **kwargs):

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

        self.handler = handler(self, *args, **kwargs)

        # Sets up the socket itself
        self.sock = socket(AF_INET, SOCK_STREAM)
        if self.secure:
            # Note: kwargs is used here to specify any SSL parameters desired
            self.sock = wrap_socket(self.sock, **kwargs)
        
        # List of all sockets involved (both client and server)
        self.sockets = list()
        self.clients = list()

        # State variable for if the server is running or not. See `run`.
        self.kill_switch = Event()
        self.imports = dict()

    def _new_client(self, sock, address):
        sock.settimeout(60)
        client_host, client_port = address
        self.sockets.append(sock)

        # Have handler process new client event
        cast(self.handler, "open_client", client_host, client_port)

        # Spawn new thread for client
        event = self.kill_switch
        client_thread = Thread(target=self._client_thread, args=(sock, event))
        self.clients.append(client_thread)
        client_thread.start()

    # Logic for the client socket running in its own thread
    def _client_thread(self, sock, kill_switch):
        while not kill_switch.is_set():
            try:
                message = self.get_message(sock)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                cast(self.handler, "close_client", sock)
                break
            if message is None:
                continue
            # Each message returns a status code, exactly which code is 
            # determined by the handler
            cast(self.handler, "message", sock, message)
        self.close_sock(sock)
        return

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

    # Closes a connected socket and removes it from the sockets list
    def close_sock(self, sock):
        if sock in self.sockets:
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
    def get_message(self, sock):
        raw_message_size = self.receive_bytes(sock, 4, False)
        if raw_message_size is None:
            return None
        message_size = unpack(">I", raw_message_size)[0]
        return self.receive_bytes(sock, message_size)

    # Packages a message and sends it to socket
    def send_message(self, sock, message, *args):
        formatted = cast(self.handler, "format", message, *args)
        try:
            sock.send(formatted)
        # The socket can either be broken or no longer open at all
        except (BrokenPipeError, OSError) as e:
            self.close_sock(sock)

    # Like send_message, but sends to all sockets but the server and the sender
    def broadcast_message(self, client_sock, client_message, *args):
        for sock in self.sockets:
            not_server = sock != self.sock
            not_client = sock != client_sock
            if not_server and not_client:
                self.send_message(sock, client_message, *args)

    def from_actor(self, imports):
        cast(self.handler, "load", imports)

    # The Process function for running the socket server logic loop
    def start(self):
        err = self._prepare()
        if err is not None:
            eprint(err)
            return err
        # print("Server ready!")
        while not self.kill_switch.is_set():
            broken = cast(self.handler, "pre_process")
            if broken:
                break
            try:
                # Accept new socket client
                client_sock, client_address = self.sock.accept()
                self._new_client(client_sock, client_address)
            # The socket can either be broken or no longer open at all
            except (BrokenPipeError, OSError) as e:
                continue
            # cast(self.handler, "post_process")

    # Stop the socket server
    def stop(self, done=None, join=False):
        cast(self.handler, "close")
        for sock in self.sockets:
            if sock != self.sock:
                sock.close()
        self.kill_switch.set()
        self.sock.close()
        if join:
            for client in self.clients:
                client.join()
        cast(done, "set")