from abots.helpers import eprint, cast

from multiprocessing import Process, Event, Queue
from enum import Enum

class MailCode(Enum):
    NORMAL = 2
    URGENT = 3
    CRITICAL = 5

    SENDER = 7
    NO_SENDER = 11

class Ledger:
    def __init__(self, entries=list(), pids=dict()):
        self.entries = entries
        self.pids = pids

    def _size(self):
        return len(self.entries)

    def get_pid(self, name):
        return self.pids.get(name, None)

    def get_by_pid(self, pid):
        if pid >= self._size():
            return None
        entry = self.entries[pid]
        event, queue = entry
        if event.is_set():
            return None
        return event, queue

    def get(self, name):
        pid = self.get_pid(name)
        if pid is None:
            return None
        return self.get_by_pid(pid)

    def register(self, name):
        if self.get_pid(name) is not None:
            return None
        pid = self._size()
        event = Event()
        queue = Queue()
        self.entries.append((event, queue))
        self.pids[name] = pid
        return pid

class Envelope:
    def __init__(self, pid, ledger, envelope=None):
        self.pid = pid
        self.ledger = ledger
        self.code = None
        self.header = None
        self.message = None
        self.sender = None
        self.valid = True
        self.can_reply = False
        self.can_deliver = False
        if envelope is not None:
            self.allowed = self.parse(envelope)

    def parse(self, envelope):
        if len(envelope) != 3:
            self.valid = False
            return None
        code, header, message = envelope
        self.code = code
        self.header = header
        self.message = message
        self.sender = self.code % MailCode.SENDER == 0 and len(self.header) == 2
        if self.sender:
            self.can_reply = True
            from_pid, to_pid = header
            if to_pid != self.pid:
                self.can_deliver = True
        allowed = dict()
        allowed["reply"] = self.can_reply
        allowed["deliver"] = self.can_deliver
        return allowed

    def get_code(self, urgent, critical, sender=True):
        code = MailCode.SENDER if sender else MailCode.NO_SENDER
        if critical:
            code = code * MailCode.CRITICAL
        elif urgent:
            code = code * MailCode.URGENT
        else:
            code = code * MailCode.NORMAL
        return code

    def compose(self, target, code, header, message):
        if type(target) != int:
            entry = self.ledger.get(target)
        else:
            entry = self.ledger.get_by_pid(target)

        if entry is None:
            return None
        event, queue = entry
        envelope = code, header, message
        queue.put(envelope)
        return True

    def send(self, to_pid, message, urgent=False, critical=False):
        code = self.get_code(urgent, critical)
        header = self.pid, to_pid
        return self.compose(to_pid, code, header, message)

    def send_to(self, to_pid, message, urgent=False, critical=False):
        code = self.get_code(urgent, critical, sender=False)
        return self.compose(to_pid, code, to_pid, message)

    def send_faux(self, faux_from_pid, faux_to_pid, to_pid, message, 
        urgent=False, critical=False):
        code = self.get_code(urgent, critical)
        header = faux_from_pid, to_pid
        return self.compose(faux_to_pid, code, header, message)
            
    def reply(self, message, urgent=False, critical=False, 
        deliver=False):
        if not self.can_reply or (deliver and not self.can_deliver):
            return None
        from_pid, to_pid = self.header
        code = self.get_code(urgent, critical)
        if deliver:
            return self.compose(to_pid, code, header, message)
        else:
            header = to_pid, from_pid
            return self.compose(from_pid, code, header, message)

    def deliver(self, message, urgent=False, critical=False):
        return self.reply(message, urgent, critical, deliver=True)

class Actor(Process):
    def __init__(self, name, proc, pid, ledger):
        super().__init__()

        self.name = name
        self.proc = proc
        self.own_pid = pid
        self.ledger = ledger
        self.valid = False
        self.kill_switch = None
        self.mailbox = None
        
        entry = self.ledger.get_by_pid(self.own_pid)
        if entry is not None:
            event, queue = entry
            self.kill_switch = event
            self.mailbox = queue
            self.valid = True

    def _call(self, source, method, *args, **kwargs):
        source_method = getattr(source, method, noop)
        try:
            return source_method(*args, **kwargs)
        except Exception:
            status = print_exc()
            eprint(status)
            return status

    def run(self):
        # print(f"Starting {self.name}")
        if not self.valid:
            return None
        # print(f"[{self.name}]: Starting proc")
        exports = dict()
        exports["pid"] = self.pid
        exports["kill_switch"] = self.kill_switch
        exports["mailbox"] = self.mailbox
        exports["ledger"] = self.ledger
        cast(self.proc, "from_actor", exports)
        proc = Process(target=self.proc.start)
        proc.start()
        actions = ["reply", "deliver", "send", "send_to", "send_faux"]
        # print(f"[{self.name}]: Started proc")
        self.kill_switch.wait()
        # while not self.kill_switch.is_set():
        #     while not self.mailbox.empty():
        #         envelope = Envelope(self.own_pid, self.mailbox.get())
        #         if not envelope.valid:
        #             continue
        #         response = cast(self.proc, "handle", envelope.message)
        #         if response is None or len(response) != 3:
        #             continue
        #         action, args, kwargs = response
        #         if action not in actions:
        #             continue
        #         elif action == "reply" and not envelope.can_reply:
        #             continue
        #         elif action == "deliver" and not envelope.can_deliver:
        #             continue
        #         cast(envelope, action, *args, **kwargs)
        self.stop()

    def stop(self, done=None, timeout=None):
        # print(f"Stopping {self.name}")
        delay = Event()
        cast(self.proc, "stop", delay)
        delay.wait(timeout)
        self.kill_switch.set()
        self.mailbox.close()
        self.mailbox.join_thread()
        cast(done, "set")
        # print(f"Stopped {self.name}")

class Supervisor:
    def __init__(self, name="__ROOT__", ledger=Ledger()):
        self.ledger = ledger
        self.children = set()
        self.pid = self.ledger.register(name)

    def call(self, source, method, *args, **kwargs):
        source_method = getattr(source, method, noop)
        try:
            return source_method(*args, **kwargs)
        except Exception:
            status = print_exc()
            eprint(status)
            return status

    def spawn(self, name, proc):
        pid = self.ledger.register(name)
        if pid is None:
            return None
        self.children.add(pid)
        actor = Actor(name, proc, pid, self.ledger)
        return actor

    def dismiss(self, child, done=None):
        # print(f"Dismissing {child}")
        if type(child) != int:
            child = self.ledger.get_pid(child)
        if child not in self.children:
            return None
        entry = self.ledger.get_by_pid(child)
        if entry is None:
            return None
        event, queue = entry
        event.set()
        queue.close()
        queue.join_thread()
        cast(done, "set")
        # print(f"Dismissed {child}")

    def stop(self, done=None):
        for child in self.children:
            self.dismiss(child)
        entry = self.ledger.get_by_pid(self.pid)
        if entry is None:
            return None
        event, queue = entry
        event.set()
        queue.close()
        queue.join_thread()
        cast(done, "set")