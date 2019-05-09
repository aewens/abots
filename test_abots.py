#!env/bin/python3

from abots.net import SocketServer, SocketClient

host = "localhost"
port = 10401
timeout = 3

server = SocketServer(host, port, timeout=timeout)
client = SocketClient(host, port, timeout=timeout)

server.start()
server.ready.wait()
client.start()