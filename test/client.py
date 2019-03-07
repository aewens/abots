#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

from abots.net import SocketClient

host = "127.0.0.1"
port = 10701

client = SocketClient(host, port)
client.daemon = True
client.start()