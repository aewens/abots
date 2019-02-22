#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

from abots.net import SocketServer, SocketClient
from multiprocessing import Process
from time import sleep

host = "127.0.0.1"
port = 10701

server = SocketServer(host, port)
server.start()
# pserver = Process(target=lambda x: x.start(), args=(server,))
# pserver.start()
# sleep(1)
# if type(input("Start client: ")) is str:
#     client = SocketClient(host, port)
#     client.start()
