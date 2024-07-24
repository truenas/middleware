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
    try:
        remote_addr, remote_port = request.transport.get_extra_info("peername")
    except Exception:
        # request can be NoneType or request.transport could be NoneType as well
        return "", ""

    if remote_addr in ["127.0.0.1", "::1"]:
        try:
            x_real_remote_addr = request.headers["X-Real-Remote-Addr"]
            x_real_remote_port = int(request.headers["X-Real-Remote-Port"])
        except (KeyError, ValueError):
            pass
        else:
            try:
                with open("/var/run/nginx.pid") as f:
                    nginx_pid = int(f.read().strip())
            except Exception:
                pass
            else:
                try:
                    process = psutil.Process(nginx_pid)
                except psutil.ProcessNotFound:
                    pass
                else:
                    if process.name() == "nginx":
                        for worker in process.children():
                            for connection in worker.connections(kind="tcp"):
                                if connection.laddr == addr(remote_addr, remote_port):
                                    remote_addr = x_real_remote_addr
                                    remote_port = x_real_remote_port

    return remote_addr, remote_port
