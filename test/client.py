#!env/bin/python3

import sys
sys.path.insert(0, "/center/lib")

from abots.net import SocketClient
from multiprocessing import JoinableQueue, Queue

inbox = JoinableQueue()
outbox = Queue()
client = SocketClient("127.0.0.1", 10701, inbox=inbox, outbox=outbox)
client.send("LIST")
client.start()