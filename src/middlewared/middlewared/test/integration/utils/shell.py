import json
import logging
import re
import time

import websocket

from middlewared.test.integration.utils import websocket_url

logger = logging.getLogger(__name__)

ansi_escape_8bit = re.compile(br"(?:\x1B[<-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[<-~])")


def assert_shell_works(token, username="root"):
    if username == "root":
        prompt = "# "
    else:
        prompt = "% "

    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps({"token": token}))
        resp_opcode, msg = ws.recv_data()
        assert json.loads(msg.decode())["msg"] == "connected", msg

        for i in range(60):
            resp_opcode, msg = ws.recv_data()
            msg = ansi_escape_8bit.sub(b"", msg).decode("ascii")
            logger.debug("Received 1 %r", msg)
            if msg.endswith(prompt):
                break

        ws.send_binary(b"whoami\n")

        for i in range(60):
            resp_opcode, msg = ws.recv_data()
            msg = ansi_escape_8bit.sub(b"", msg).decode("ascii")
            logger.debug("Received 2 %r", msg)
            if username in msg.split():
                break
    finally:
        ws.close()
        # Give middleware time to kill user's zsh on connection close (otherwise, it will prevent user's home directory
        # dataset from being destroyed)
        time.sleep(5)
