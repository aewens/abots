from abots.net.socket_server_handler import SocketServerHandler

from threading import Thread
from struct import pack, unpack
from select import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from multiprocessing import Process, Queue, JoinableQueue

class SocketServer(Process):
    def __init__(self, host, port, listeners=5, buffer_size=4096,       
        max_message_size=26214400, end_of_line="\r\n", inbox=JoinableQueue(),
        outbox=Queue(), handler=None):
        Process.__init__(self)

        self.host = host
        self.port = port
        self.listeners = listeners
        self.buffer_size = buffer_size
        self.max_message_size = max_message_size
        self.end_of_line = end_of_line
        self.inbox = inbox
        self.outbox = outbox
        self.handler = SocketServerHandler if handler is None else handler
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock_fd = -1
        self.lookup = list()
        self.sockets = list()
        self.clients = dict()
        self.running = True

    def _close_sock(self, sock):
        self.sockets.remove(sock)
        fd = self._get_client_fd(sock)
        if fd is not None:
            del self.clients[fd]
        sock.close()

    def _recv_bytes(self, sock, get_bytes, decode=True):
        data = "".encode()
        eol = self.end_of_line.encode()
        if get_bytes > self.max_message_size:
            return None
        attempts = 0
        while len(data) < get_bytes:
            if attempts > self.max_message_size / self.buffer_size:
                break
            else:
                attempts = attempts + 1
            bufsize = get_bytes - len(data)
            if bufsize > self.buffer_size:
                bufsize = self.buffer_size
            try:
                packet = sock.recv(bufsize)
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

    def _get_message_size(self, sock):
        raw_message_size = self._recv_bytes(sock, 4, False)
        if not raw_message_size:
            return None
        message_size = unpack(">I", raw_message_size)[0]
        return message_size

    def _get_message(self, sock):
        message_size = self._get_message_size(sock)
        if message_size is None:
            return None
        elif message_size > self.max_message_size:
            return None
        try:
            return self._recv_bytes(sock, message_size).strip(self.end_of_line)
        except OSError:
            self._close_sock(sock)
            return None

    def _send_message(self, sock, message, *args):
        packaged = self._package_message(message, *args)
        try:
            sock.send(packaged)
        except BrokenPipeError:
            self._close_sock(sock)
        except OSError:
            self._close_sock(sock)

    def _broadcast_message(self, client_sock, client_message, *args):
        for sock in self.sockets:
            not_server = sock != self.sock
            not_client = sock != client_sock
            if not_server and not_client:
                self._send_message(sock, client_message, *args)

    def _get_client_fd(self, client_sock):
        try:
            return client_sock.fileno()
        except OSError:
            for fd, sock in self.lookup:
                if sock != client_sock:
                    continue
                return fd
            return None

    def _process_inbox(self):
        while not self.inbox.empty():
            data = self.inbox.get()
            mode = data[0]
            if mode == "SEND":
                client, message, args = data[1:]
                self._send_message(message, *args)
            elif mode == "BCAST":
                message, args = data[1:]
                self._broadcast_message(self.sock, message, *args)
            self.inbox.task_done()

    def _client_thread(self, sock):
        while self.running:
            message = self._get_message(sock)
            if message is None:
                continue
            status = self.handler(self, sock, message)
            self.outbox.put((status, message))

    def _prepare(self):
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.host, self.port))
        except OSError as e:
            return e
        self.sock.listen(self.listeners)
        self.sock_fd = self.sock.fileno()
        sock_address = self.sock.getsockname()
        sock_host, sock_port = sock_address
        self.lookup.append((self.sock_fd, sock_address))
        self.sockets.append(self.sock)
        self.clients[self.sock_fd] = dict()
        self.clients[self.sock_fd]["host"] = sock_host
        self.clients[self.sock_fd]["port"] = sock_port
        self.clients[self.sock_fd]["sock"] = self.sock
        return None

    def send(self, client, message, *args):
        self.inbox.put(("SEND", client, message, args))

    def broadcast(self, message, *args):
        self.inbox.put(("BCAST", message, args))

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
        print("Server ready!")
        while self.running:
            # try:
            #     selection = select(self.sockets, list(), list(), 5)
            #     read_socks, write_socks, err_socks = selection
            # except OSError as e:
            #     print("Error", e)
            #     continue
            # for sock in read_socks:
            #     if sock == self.sock:
            try:
                client_sock, client_address = self.sock.accept()
                client_sock.settimeout(60)
            except OSError:
                continue
            client_name = "{}:{}".format(*client_address)
            client_host, client_port = client_address
            client_fd = client_sock.fileno()
            self.lookup.append((client_fd, client_sock))
            self.sockets.append(client_sock)
            self.clients[client_fd] = dict()
            self.clients[client_fd]["host"] = client_host
            self.clients[client_fd]["port"] = client_port
            self.clients[client_fd]["sock"] = client_sock
            joined = "ENTER {}".format(client_name)
            self.outbox.put((1, joined))
            self._broadcast_message(client_sock, joined)
            Thread(target=self._client_thread, args=(client_sock,)).start()
            #     else:
            #         message = self._get_message(sock)
            #         if message is None:
            #             continue
            #         status = self.handler(self, sock, message)
            #         self.outbox.put((status, message))

    def stop(self):
        self.running = False
        self.sock.close()