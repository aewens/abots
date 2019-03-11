"""

Socket Server Handlers
======================

The socket server was made to be versitile where the handler can be swapped out 
in favor of another handler. This handler is the default provided if one is not 
passed to get the basic client-server relationship working for either starting 
with something simple, testing, and/or providing a template to build other 
handlers from.

"""

class SocketServerHandler:
    def __init__(self, server):
        self.server = server

        # These are used when processing inbox messages
        self.send_verb = "SEND"
        self.broadcast_verb = "CAST"

        self.close_verb = "STOP"

    # Tells all clients that a node joined the socket server
    def open_client(self, alias):
        alias = message[5:]
        client = self.server.clients.get(alias, None)
        if client is None:
            return 1
        self.server.broadcast_message(client, message)
        return 0

    # Informs the other clients a client left and closes that client's socket
    def close_client(self, alias):
        client = self.server.clients.get(alias, None)
        if client is None:
            return 1
        message = "LEFT {}".format(alias)
        self.server.broadcast_message(self.server.sock, message)
        self.server.close_sock(alias)
        return 0

    # Lets the clients know the server is intentionally closing
    def close_server(self):
        self.server.broadcast_message(self.server.sock, self.close_verb)
        return -1

    # Sends a heartbeat to the client to detect if it is still responding
    def send_heartbeat(self, alias):
        client = self.server.clients.get(alias, None)
        if client is None:
            return 1
        sock = client.get("sock", None)
        if sock is None:
            return 1
        self.server.send_message(sock, "PING")
        return 0

    # Format a message before sending to client(s)
    # Prepends message size code along with replacing variables in message
    def format_message(self, message, *args):
        formatted = None
        if len(args) > 0:
            formatted = message.format(*args) + self.server.end_of_line
        else:
            formatted = message + self.server.end_of_line
        
        # Puts message size at the front of the message
        prefixed = pack(">I", len(formatted)) + formatted.encode()
        return prefixed

    # Get message from socket with `format_message` in mind
    def get_message(self, sock):
        raw_message_size = self.server.receive_bytes(sock, 4, False)
        if raw_message_size is None:
            return None
        message_size = unpack(">I", raw_message_size)[0]
        if self.max_message_size > 0 and message_size > self.max_message_size:
            return None
        eol = self.server.end_of_line
        return self.server.receive_bytes(sock, message_size).strip(eol)

    # Takes the server object, the client socket, and a message to process
    # Each message returns a status code:
    # -1 : Going offline
    #  0 : Success
    #  1 : Failure
    #  2 : Invalid
    def message(self, sock, message):
        # print("DEBUG:", message)

        send = self.send_verb + " "
        cast = self.broadcast_verb + " "
        send_size = len(send)
        cast_size = len(cast)

        # React to heartbeat from client
        if message == "PONG":
            client_fd = self.server.get_client_fd(sock)
            client = self.server.clients.get(client_fd, dict())
            client_alive = client.get("alive", None)
            if client_aliave is None:
                return 1
            elif client_alive:
                return 1
            # Setting this to True is what tells the server the heartbeat worked
            client["alive"] = True
            return 0

        # Tell the clients to stop before server itself stops
        elif message == self.close_verb:
            status = self.close_server()
            self.server.stop()
            return status

        # Informs the other clients one left and closes that client's socket
        elif message == "QUIT":
            client_alias = self.server.get_client_alias_by_sock(sock)
            if client_alias is None:
                return 1
            return self.close_client(client_alias)

        # Lists all client alises, puts itself first and the server second
        elif message == "LIST":
            aliases = list()
            client_alias = self.server.get_client_alias_by_sock(sock)
            if client_alias is None:
                return 1
            self.server_alias = self.server.sock_alias
            for alias in self.server.clients.keys():
                # We need to skip ints since the file descriptors are also keys
                if type(alias) is int:
                    continue
                # The server and sending client are skipped to retain ordering
                elif alias == self.server.sock_alias:
                    continue
                elif alias == client_alias:
                    continue
                else:
                    aliases.append(alias)
            listed = ",".join([client_alias, self.server_alias] + aliases)
            self.server.send_message(sock, listed)
            return 0

        # Sends a message to the client with the specified client (via an alias)
        elif message[:send_size] == send:
            params = message[(send_size + 1):].split(" ", 1)
            if len(params) < 2:
                return 1
            alias, response = params
            client = self.server.clients.get(alias, dict())
            client_sock = client.get("sock", None)
            if client_sock is None:
                return 1
            self.server.send_message(client_sock, response)
            return 0

        # Broadcasts a message to all other clients
        elif message[:cast_size] == cast:
            response = message[(cast_size + 1):]
            self.server.broadcast_message(sock, response)
            return 0

        # All other commands are invalid
        else:
            return 2