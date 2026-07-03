from __future__ import annotations

import os
import subprocess
import tempfile

from middlewared.api.current import KeychainCredentialRemoteSshHostKeyScanArgs, SSHKeyPair
from middlewared.service_exception import CallError
from middlewared.utils import run


def generate_ssh_key_pair() -> SSHKeyPair:
    with tempfile.TemporaryDirectory() as tmpdirname:
        key = os.path.join(tmpdirname, "key")
        subprocess.check_call(["ssh-keygen", "-t", "rsa", "-f", key, "-N", "", "-q"])
        with open(key) as f:
            private_key = f.read()
        with open(f"{key}.pub") as f:
            public_key = f.read()

    return SSHKeyPair(
        private_key=private_key,
        public_key=public_key,
    )


async def remote_ssh_host_key_scan(data: KeychainCredentialRemoteSshHostKeyScanArgs) -> str:
    proc = await run(
        ["ssh-keyscan", "-p", str(data.port), "-T", str(data.connect_timeout), data.host], check=False, encoding="utf8"
    )
    if proc.returncode == 0:
        if proc.stdout:
            try:
                return process_ssh_keyscan_output(proc.stdout)
            except Exception:
                raise CallError(f"ssh-keyscan failed: {proc.stdout + proc.stderr}") from None
        elif proc.stderr:
            raise CallError(f"ssh-keyscan failed: {proc.stderr}")
        else:
            raise CallError("SSH timeout")
    else:
        raise CallError(f"ssh-keyscan failed: {proc.stdout + proc.stderr}")


def process_ssh_keyscan_output(output: str) -> str:
    return "\n".join([" ".join(line.split()[1:]) for line in output.split("\n") if line and not line.startswith("# ")])
