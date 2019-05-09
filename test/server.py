#!env/bin/python3

import sys
from os.path import dirname, realpath

source = "/".join(dirname(realpath(__file__)).split("/")[:-1])
sys.path.insert(0, source)

from abots.net import SocketServer

host = "127.0.0.1"
port = 10701
timeout = 3

server = SocketServer(host, port, timeout=timeout)
server.daemon = True
server.start()