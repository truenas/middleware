import dataclasses
import logging
import os
import socket

logger = logging.getLogger(__name__)

__all__ = ("SystemdNotifier",)


@dataclasses.dataclass(slots=True)
class SystemdNotifier:
    _socket: socket.socket | None = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        addr = os.getenv("NOTIFY_SOCKET")
        if not addr:
            return

        if addr.startswith("@"):
            addr = f"\0{addr[1:]}"

        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.connect(addr)
            self._socket = sock
        except Exception:
            if sock is not None:
                sock.close()
            self._socket = None
            logger.exception("Failed to connect to systemd socket")

    def notify(self, msg: str) -> None:
        if self._socket is None:
            return

        try:
            self._socket.send(msg.encode("latin-1"))
        except Exception:
            logger.exception("Failed to send message %r", msg)

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                logger.exception("Error closing systemd socket")
            finally:
                self._socket = None
