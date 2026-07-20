"""A minimal SMTP server used by the integration test-suite.

It speaks just enough of the SMTP protocol to accept a message and records the
envelope (``MAIL FROM`` / ``RCPT TO``) together with the raw RFC822 message as a
JSON file per email in the output directory. It is meant to be uploaded to and
run on a TrueNAS host so that ``mail.send`` can deliver to it over ``127.0.0.1``
without a real MTA or outbound network access.

Usage: ``python3 smtp.py <output_directory> <port>``
"""
import json
import os
import re
import socket
import sys
import threading
import time

ADDR_RE = re.compile(r"<([^>]*)>")


def _address(command):
    match = ADDR_RE.search(command)
    return match.group(1) if match else command.split(":", 1)[-1].strip()


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
        if upper.startswith(("EHLO", "HELO")):
            reply("250 fakesmtp")
        elif upper.startswith("MAIL FROM"):
            mail_from = _address(command)
            reply("250 OK")
        elif upper.startswith("RCPT TO"):
            rcpt_to.append(_address(command))
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
