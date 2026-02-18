import json
import logging
import re
import time

import websocket

from middlewared.test.integration.utils import call, websocket_url

logger = logging.getLogger(__name__)

ansi_escape_8bit = re.compile(br"(?:\x1B[<-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[<-~])")


def webshell_exec(command: str | bytes, token=None, username="root", timeout=10):
    """
    Execute a command through the webshell and return the output.

    Args:
        command: Command to execute (e.g., "whoami" or "midclt call system.info")
        token: Authentication token (if None, will generate one)
        username: Username for the shell (default: "root")
        timeout: WebSocket timeout in seconds

    Returns:
        str: Command output with ANSI escape codes removed
    """
    if token is None:
        token = call('auth.generate_token', 300, {}, True)

    if username == "root":
        prompt = b"# "
    else:
        prompt = b"% "

    ws = websocket.create_connection(websocket_url() + "/websocket/shell", timeout=timeout)
    try:
        # Authenticate with token
        ws.send(json.dumps({"token": token}))
        resp_opcode, msg = ws.recv_data()
        auth_response = json.loads(msg.decode())
        assert auth_response["msg"] == "connected", f"Authentication failed: {auth_response}"

        # Wait for shell prompt
        for _ in range(60):
            resp_opcode, msg = ws.recv_data()
            clean_msg = ansi_escape_8bit.sub(b"", msg)
            logger.debug("Waiting for prompt, received: %r", clean_msg)
            # Handle zsh first-run message
            if b"You are seeing this message because you have no zsh startup files" in clean_msg:
                ws.send_binary(b"q\n")
            if clean_msg.endswith(prompt):
                break

        # Send the command
        if isinstance(command, str):
            command = command.encode()
        ws.send_binary(command)
        if not command.endswith(b"\n"):
            ws.send_binary(b"\n")

        # Read output until we see the prompt again
        output = b""
        for _ in range(60):
            resp_opcode, msg = ws.recv_data()
            output += msg
            clean_output = ansi_escape_8bit.sub(b"", msg)
            logger.debug("Command output received: %r", clean_output)
            if clean_output.endswith(prompt):
                break

        # Clean ANSI codes from final output
        clean_output = ansi_escape_8bit.sub(b"", output).decode("ascii", errors="ignore")
        return clean_output
    finally:
        ws.close()
        # Give middleware time to kill user's zsh on connection close (otherwise, it will prevent user's home directory
        # dataset from being destroyed)
        time.sleep(5)


def assert_shell_works(token, username="root"):
    """
    Assert that a webshell session works with the given token.

    Connects to the webshell, runs 'whoami', and verifies the username appears in the output.
    """
    output = webshell_exec("whoami", token=token, username=username, timeout=10)
    assert username in output.split()
