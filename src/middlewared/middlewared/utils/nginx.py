# -*- coding=utf-8 -*-
import psutil
from psutil._common import addr


def get_peer_process(remote_addr, remote_port):
    for connection in psutil.net_connections(kind='tcp'):
        if connection.laddr == addr(remote_addr, remote_port):
            try:
                return psutil.Process(connection.pid)
            except psutil.ProcessNotFound:
                return None


def get_remote_addr_port(request):
    remote_addr, remote_port = request.transport.get_extra_info("peername")
    if remote_addr in ["127.0.0.1", "::1"]:
        try:
            x_real_remote_addr = request.headers["X-Real-Remote-Addr"]
            x_real_remote_port = int(request.headers["X-Real-Remote-Port"])
        except (KeyError, ValueError):
            pass
        else:
            if process := get_peer_process(remote_addr, remote_port):
                if process.name() == "nginx":
                    try:
                        with open("/var/run/nginx.pid") as f:
                            nginx_pid = int(f.read().strip())
                    except Exception:
                        pass
                    else:
                        try:
                            ppid = process.ppid()
                        except psutil.ProcessNotFound:
                            pass
                        else:
                            if ppid == nginx_pid:
                                remote_addr = x_real_remote_addr
                                remote_port = x_real_remote_port

    return remote_addr, remote_port
