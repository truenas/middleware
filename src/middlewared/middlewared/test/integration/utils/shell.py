import json
import logging
import re
import time

import websocket

from middlewared.test.integration.utils import call, websocket_url

logger = logging.getLogger(__name__)

ansi_escape_8bit = re.compile(br"(?:\x1B[<-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[<-~])")

# zsh shows an interactive first-run menu when the account has no zsh startup
# files; it must be dismissed with `q` before the shell is usable.
ZSH_FIRST_RUN = b"You are seeing this message because you have no zsh startup files"

# Sentinels bracketing the command output. The form we *type* splices in an
# empty string (`""`) so the echoed command line never contains the assembled
# marker -- only the shell's evaluation of `echo` emits it. Reading until the
# assembled OUT_END (rather than a bare prompt) makes output capture immune to
# zsh prompt redraws, which otherwise get mistaken for the end of output and
# truncate the result before the command has even run.
OUT_START_TYPED = b'TN_WS_OUT""_START'
OUT_START = b"TN_WS_OUT_START"
OUT_END_TYPED = b'TN_WS_OUT""_END'
OUT_END = b"TN_WS_OUT_END"

def webshell_exec(command: str | bytes, token=None, username="root", timeout=10):
    """
    Execute a command through the webshell and return its output.

    Args:
        command: Command to execute (e.g., "whoami" or "midclt call system.info")
        token: Authentication token (if None, will generate one)
        username: Username for the shell (default: "root"); selects the expected
            prompt character (root uses "# ", others "% ")
        timeout: WebSocket timeout in seconds

    Returns:
        str: Command output with ANSI escape codes removed, captured between
        sentinels so it excludes the prompt and the echoed command line.
    """
    if token is None:
        token = call('auth.generate_token', 300, {}, True)

    prompt = b"# " if username == "root" else b"% "

    if isinstance(command, bytes):
        command = command.decode()
    command = command.rstrip("\n")

    ws = websocket.create_connection(websocket_url() + "/websocket/shell", timeout=timeout)
    try:
        # Authenticate with token
        ws.send(json.dumps({"token": token}))
        resp_opcode, msg = ws.recv_data()
        auth_response = json.loads(msg.decode())
        assert auth_response["msg"] == "connected", f"Authentication failed: {auth_response}"

        # Wait for the shell prompt before sending anything; the shell isn't
        # ready to receive input until then. Dismiss the zsh first-run menu if
        # it appears.
        for _ in range(60):
            resp_opcode, msg = ws.recv_data()
            clean_msg = ansi_escape_8bit.sub(b"", msg)
            logger.debug("Waiting for prompt, received: %r", clean_msg)
            if ZSH_FIRST_RUN in clean_msg:
                ws.send_binary(b"q\n")
            if clean_msg.endswith(prompt):
                break

        # Bracket the command with sentinels and read until the closing marker
        # rather than a prompt, so prompt redraws can't be mistaken for the end
        # of output.
        ws.send_binary(
            b"echo " + OUT_START_TYPED + b"; " + command.encode() + b"; echo " + OUT_END_TYPED + b"\n"
        )

        output = b""
        for _ in range(120):
            resp_opcode, msg = ws.recv_data()
            output += msg
            if OUT_END in ansi_escape_8bit.sub(b"", output):
                break
        else:
            raise AssertionError(f"webshell: command output not terminated: {output!r}")

        clean = ansi_escape_8bit.sub(b"", output)
        # The echoed command line only contains the spliced *_TYPED markers, so
        # the first assembled OUT_START / OUT_END are the echo's own output.
        body = clean.split(OUT_START, 1)[1].split(OUT_END, 1)[0]
        return body.decode("ascii", errors="ignore")
    finally:
        ws.close()
        # Give middleware time to kill the user's zsh on connection close,
        # otherwise it can block destruction of the user's home directory dataset.
        time.sleep(5)


def assert_shell_works(token, username="root"):
    """
    Assert that a webshell session works with the given token.

    Connects to the webshell, runs 'whoami', and verifies the username appears in the output.
    """
    output = webshell_exec("whoami", token=token, username=username)
    assert username in output.split(), output
