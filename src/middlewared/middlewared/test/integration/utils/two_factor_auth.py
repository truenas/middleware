import dataclasses

import paramiko

from .client import truenas_server

__all__ = ["OATH_PROMPT", "PASSWORD_PROMPT", "SshAuthResult", "ssh_auth_with_otp"]

OATH_PROMPT = "One-time password (OATH)"
PASSWORD_PROMPT = "Password: "


@dataclasses.dataclass
class SshAuthResult:
    authenticated: bool
    prompts: list[str]


def ssh_auth_with_otp(username: str, password: str, otp_token: str = "", ip: str | None = None) -> SshAuthResult:
    """Log `username` in over SSH, answering the PAM prompts of the keyboard-interactive method.

    `prompts` lists every prompt PAM asked for, in order. pam_oath only prompts for a token when
    /etc/users.oath holds an entry for the user, and only accepts a token derived from the secret
    in that entry. A successful result therefore proves that the file the running sshd reads is
    up to date.

    `ip` defaults to the server under test. Pass the standby controller address to check an HA
    node that replicates its configuration from the active one.
    """
    ip = ip or truenas_server.ip
    prompts = []

    def handler(title, instructions, prompt_list):
        answers = []
        for prompt, _echo in prompt_list:
            prompts.append(prompt)
            if OATH_PROMPT in prompt:
                answers.append(otp_token)
            else:
                answers.append(password)

        return answers

    transport = paramiko.Transport((ip, 22))
    try:
        transport.connect()
        transport.auth_interactive(username, handler)
        authenticated = True
    except paramiko.AuthenticationException:
        authenticated = False
    finally:
        transport.close()

    return SshAuthResult(authenticated, prompts)
