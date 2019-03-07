#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

from abots.net import SocketServer

host = "127.0.0.1"
port = 10701

server = SocketServer(host, port)
server.daemon = True
server.start()