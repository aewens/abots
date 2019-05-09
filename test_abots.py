#!env/bin/python3

from abots.net import SocketServer, SocketClient
from abots.events import ThreadMarshal

pool_size = 2
marshal = ThreadMarshal(2)
server = SocketServer("localhost", 10401, timeout=3)
client = SocketClient("localhost", 10401, timeout=3)

marshal.reserve(server.start)
server.ready.wait()
marshal.reserve(client.start)