#!env/bin/python3

import sys
from os.path import dirname, realpath

source = "/".join(dirname(realpath(__file__)).split("/")[:-1])
sys.path.insert(0, source)

from abots.net import SocketClient

host = "127.0.0.1"
port = 10701
timeout = 3

client = SocketClient(host, port, timeout=timeout)
client.daemon = True
client.start()