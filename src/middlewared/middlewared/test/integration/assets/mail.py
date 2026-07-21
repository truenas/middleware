import base64
import contextlib
from dataclasses import dataclass
import email
import json
import os
import time

from middlewared.test.integration.utils import call, ssh

__all__ = ["fake_smtp_server"]

# Local path of the fake SMTP server that gets uploaded to the TrueNAS host.
_SERVER_SRC = os.path.join(os.path.dirname(__file__), "..", "fake_servers", "smtp.py")
_REMOTE_PATH = "/tmp/fake_smtp_server.py"
_OUTDIR = "/tmp/fake_smtp"
# ``[s]mtp.py`` matches the running server process but not the ``pkill`` command
# line itself (which contains the literal ``[s]``), so pkill does not kill its
# own SSH session.
_KILL_PATTERN = "[f]ake_smtp_server.py"


@dataclass
class ReceivedMail:
    mail_from: str
    rcpt_to: list[str]
    message: email.message.Message


@dataclass
class FakeSMTPServer:
    host: str
    port: int

    def clear(self) -> None:
        """Discard every message recorded so far."""
        # `find` rather than a glob, which the remote shell fails on when the directory is empty.
        ssh(f"find {_OUTDIR} -type f -delete")

    def get_messages(self) -> list[ReceivedMail]:
        result = []
        for name in sorted(ssh(f"ls {_OUTDIR}").split()):
            record = json.loads(ssh(f"cat {_OUTDIR}/{name}"))
            result.append(ReceivedMail(
                mail_from=record["mail_from"],
                rcpt_to=record["rcpt_to"],
                message=email.message_from_string(record["data"]),
            ))
        return result


@contextlib.contextmanager
def fake_smtp_server(port=8025):
    with open(_SERVER_SRC, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")

    ssh(f"pkill -f '{_KILL_PATTERN}' || true")
    ssh(f"rm -rf {_OUTDIR}")
    call("filesystem.file_receive", _REMOTE_PATH, content, {"mode": 0o755})
    ssh(f"setsid python3 {_REMOTE_PATH} {_OUTDIR} {port} </dev/null >/tmp/fake_smtp.log 2>&1 &")

    # Wait for the server to start listening.
    for _ in range(20):
        if ssh(f"ss -ltn | grep ':{port} ' || true").strip():
            break
        time.sleep(0.5)
    else:
        log = ssh("cat /tmp/fake_smtp.log || true")
        raise AssertionError(f"fake SMTP server did not start listening:\n{log}")

    try:
        yield FakeSMTPServer(host="127.0.0.1", port=port)
    finally:
        ssh(f"pkill -f '{_KILL_PATTERN}' || true")
