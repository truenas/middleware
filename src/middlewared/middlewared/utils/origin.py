class Origin:
    def match(self, origin):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class UnixSocketOrigin(Origin):
    def __init__(self, pid, uid, gid):
        self.pid = pid
        self.uid = uid
        self.gid = gid

    def match(self, origin):
        return self.uid == origin.uid and self.gid == origin.gid

    def __str__(self):
        return f"UNIX socket (pid={self.pid} uid={self.uid} gid={self.gid})"


class TCPIPOrigin(Origin):
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

    def match(self, origin):
        return self.addr == origin.addr

    def __str__(self):
        if ":" in self.addr:
            return f"[{self.addr}]:{self.port}"
        else:
            return f"{self.addr}:{self.port}"
