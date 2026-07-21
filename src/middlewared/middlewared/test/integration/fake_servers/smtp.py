"""A minimal SMTP server used by the integration test-suite.

It speaks just enough of the SMTP protocol to accept a message and records the
envelope (``MAIL FROM`` / ``RCPT TO``) together with the raw RFC822 message as a
JSON file per email in the output directory. It is meant to be uploaded to and
run on a TrueNAS host so that ``mail.send`` can deliver to it over ``127.0.0.1``
without a real MTA or outbound network access.

Besides plain delivery it supports ``AUTH PLAIN``/``AUTH LOGIN`` (see ``AUTH_USER``
and ``AUTH_PASSWORD``) and rejects any envelope address containing ``REFUSE_SENDER``
or ``REFUSE_RECIPIENT`` so that the SMTP error handling paths can be tested.

Usage: ``python3 smtp.py <output_directory> <port>``
"""
import base64
import json
import os
import re
import socket
import sys
import threading
import time

ADDR_RE = re.compile(r"<([^>]*)>")

AUTH_USER = "fakeuser"
AUTH_PASSWORD = "fakepassword"
# Envelope addresses containing these markers are rejected by the server.
REFUSE_SENDER = "refuse-sender"
REFUSE_RECIPIENT = "refuse-recipient"


def _address(command):
    match = ADDR_RE.search(command)
    return match.group(1) if match else command.split(":", 1)[-1].strip()


def _decode(line):
    return base64.b64decode(line.strip()).decode("utf-8", "replace")


def _authenticate(command, f, reply):
    """Run the AUTH exchange for `command`, returning whether the credentials are valid."""
    parts = command.split()
    mechanism = parts[1].upper() if len(parts) > 1 else ""
    try:
        if mechanism == "PLAIN":
            if len(parts) > 2:
                blob = parts[2]
            else:
                reply("334 ")
                blob = f.readline().decode()
            # The PLAIN payload is "authzid\0authcid\0password".
            fields = base64.b64decode(blob.strip()).decode("utf-8", "replace").split("\0")
            return len(fields) == 3 and fields[1] == AUTH_USER and fields[2] == AUTH_PASSWORD
        elif mechanism == "LOGIN":
            reply("334 " + base64.b64encode(b"Username:").decode())
            user = _decode(f.readline())
            reply("334 " + base64.b64encode(b"Password:").decode())
            password = _decode(f.readline())
            return user == AUTH_USER and password == AUTH_PASSWORD
    except Exception:
        return False

    return False


def handle(conn, outdir):
    def reply(line):
        conn.sendall((line + "\r\n").encode())

    f = conn.makefile("rb")
    reply("220 fakesmtp ready")
    mail_from = None
    rcpt_to = []
    while True:
        raw = f.readline()
        if not raw:
            break
        command = raw.decode("utf-8", "replace").rstrip("\r\n")
        upper = command.upper()
        if upper.startswith("EHLO"):
            reply("250-fakesmtp\r\n250 AUTH PLAIN LOGIN")
        elif upper.startswith("HELO"):
            reply("250 fakesmtp")
        elif upper.startswith("AUTH "):
            if _authenticate(command, f, reply):
                reply("235 2.7.0 Authentication successful")
            else:
                reply("535 5.7.8 Authentication credentials invalid")
        elif upper.startswith("MAIL FROM"):
            mail_from = _address(command)
            if REFUSE_SENDER in mail_from:
                reply("550 5.7.1 Sender rejected")
                mail_from = None
            else:
                reply("250 OK")
        elif upper.startswith("RCPT TO"):
            recipient = _address(command)
            if REFUSE_RECIPIENT in recipient:
                reply("550 5.1.1 Recipient rejected")
            else:
                rcpt_to.append(recipient)
                reply("250 OK")
        elif upper == "DATA":
            reply("354 End data with <CR><LF>.<CR><LF>")
            data = b""
            while True:
                line = f.readline()
                if not line or line in (b".\r\n", b".\n"):
                    break
                if line.startswith(b".."):  # undo SMTP dot-stuffing
                    line = line[1:]
                data += line
            record = {
                "mail_from": mail_from,
                "rcpt_to": rcpt_to,
                "data": data.decode("utf-8", "replace"),
            }
            path = os.path.join(outdir, "msg_%d.json" % time.time_ns())
            with open(path, "w") as out:
                json.dump(record, out)
            reply("250 OK: queued")
            mail_from = None
            rcpt_to = []
        elif upper.startswith("QUIT"):
            reply("221 Bye")
            break
        elif upper.startswith(("RSET", "NOOP")):
            reply("250 OK")
        else:
            reply("250 OK")
    conn.close()


def main():
    outdir = sys.argv[1]
    port = int(sys.argv[2])
    os.makedirs(outdir, exist_ok=True)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(5)
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn, outdir), daemon=True).start()


if __name__ == "__main__":
    main()
