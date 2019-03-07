def SocketServerHandler(server, sock, message):
    print("RAW:", message)
    if message == "STOP":
        server._broadcast_message(server.sock, "STOP")
        server.stop()
        return -1
    if message == "QUIT":
        client_fd = server._get_client_fd(sock)
        if client_fd is None:
            return 0
        client_address = [a for fd, a in server.lookup if fd == client_fd][0]
        client_name = "{}:{}".format(*client_address)
        server._broadcast_message(server.sock, "LEAVE {}".format(client_name))
        server._close_sock(sock)
        return 1
    elif message == "LIST":
        fds = list() #list(map(str, server.clients.keys()))
        client_fd = server._get_client_fd(sock)
        for fd in server.clients.keys():
            if fd == server.sock_fd:
                fds.append("*{}".format(fd))
            elif fd == client_fd:
                fds.append("+{}".format(fd))
            else:
                fds.append(str(fd))
        server._send_message(sock, ",".join(fds))
        return 1
    elif message[:5] == "SEND ":
        params = message[5:].split(" ", 1)
        if len(params) < 2:
            return 0
        fd, response = params
        client_sock = server.clients.get(int(fd), dict()).get("sock", None)
        if client_sock is None:
            return 0
        server._send_message(client_sock, response)
        return 1
    elif message[:6] == "BCAST ":
        response = message[6:]
        server._broadcast_message(sock, response)
        return 1
    else:
        return 2