from threading import Thread
from struct import pack, unpack
from select import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

class SocketServer(Thread):
    def __init__(self, host, port, listeners=5, buffer_size=4096,       
        max_message_size=26214400, end_of_line="\r\n", handler=None):
        Thread.__init__(self)

        self.host = host
        self.port = port
        self.listeners = listeners
        self.buffer_size = buffer_size
        self.max_message_size = max_message_size
        self.end_of_line = end_of_line
        self.handler = self._handler if handler is None else handler
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock_fd = -1
        self.lookup = list()
        self.sockets = list()
        self.clients = dict()
        self.running = True

    def _handler(self, sock, message):
        print("RAW", message)
        if message == "STOP":
            self.broadcast(self.sock, "STOP")
            self.stop()
            return -1
        if message == "QUIT":
            client_fd = self.get_client_fd(sock)
            if client_fd is None:
                return 0
            client_address = [a for fd, a in self.lookup if fd == client_fd][0]
            client_name = "{}:{}".format(*client_address)
            self.broadcast(self.sock, "LEAVE {}".format(client_name))
            self._close_sock(sock)
            return 1
        elif message == "LIST":
            fds = list() #list(map(str, self.clients.keys()))
            client_fd = self.get_client_fd(sock)
            for fd in self.clients.keys():
                if fd == self.sock_fd:
                    fds.append("*{}".format(fd))
                elif fd == client_fd:
                    fds.append("+{}".format(fd))
                else:
                    fds.append(str(fd))
            self.send(sock, ",".join(fds))
            return 1
        elif message[:5] == "SEND ":
            params = message[5:].split(" ", 1)
            if len(params) < 2:
                return 0
            fd, response = params
            client_sock = self.clients.get(int(fd), dict()).get("sock", None)
            if client_sock is None:
                return 0
            self.send(client_sock, response)
            return 1
        elif message[:6] == "BCAST ":
            response = message[6:]
            self.broadcast(sock, response)
            return 1
        else:
            return 2

    def _close_sock(self, sock):
        self.sockets.remove(sock)
        fd = self.get_client_fd(sock)
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

    def get(self, sock):
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

    def send(self, sock, message, *args):
        packaged = self._package_message(message, *args)
        try:
            sock.send(packaged)
        except BrokenPipeError:
            self._close_sock(sock)
        except OSError:
            self._close_sock(sock)

    def get_client_fd(self, client_sock):
        try:
            return client_sock.fileno()
        except OSError:
            for fd, sock in self.lookup:
                if sock != client_sock:
                    continue
                return fd
            return None

    def broadcast(self, client_sock, client_message, *args):
        for sock in self.sockets:
            not_server = sock != self.sock
            not_client = sock != client_sock
            if not_server and not_client:
                self.send(sock, client_message, *args)

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

    def start(self):
        err = self._prepare()
        if err is not None:
            print(err)
            return err
        print("Server ready!")
        while self.running:
            try:
                selection = select(self.sockets, list(), list(), 5)
                read_socks, write_socks, err_socks = selection
            except OSError as e:
                print("Error", e)
                continue
            for sock in read_socks:
                if sock == self.sock:
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
                    print(joined)
                    self.broadcast(client_sock, joined)
                else:
                    message = self.get(sock)
                    if message is None:
                        continue
                    status = self.handler(sock, message)
                    print(status, message)

    def stop(self):
        self.running = False
        self.sock.close()