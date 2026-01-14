import asyncio
import os
import shlex
import subprocess
import tempfile
from typing import Any

from middlewared.service import CallError
from middlewared.utils import Popen


def env_mapping(prefix: str, mapping: dict[str, Any]) -> dict[str, str]:
    """Return a mapping of environment variables with the given prefix."""
    env = {}

    for k, v in mapping.items():
        var_name = (prefix + k).upper()

        if isinstance(v, bool):
            env[var_name] = str(int(v))

        elif isinstance(v, (int, str)):
            env[var_name] = str(v)

    return env


async def run_script(job, script_name, hook: str = "", env: dict | None = None):
    env = env or {}

    hook = hook.strip()
    if not hook:
        return

    if hook.startswith("#!"):
        shebang = shlex.split(hook.splitlines()[0][2:].strip())
    else:
        shebang = ["/bin/bash"]

    # It is ok to do synchronous I/O here since we are operating in ramfs which will never block
    with tempfile.NamedTemporaryFile("w+") as f:
        os.chmod(f.name, 0o700)
        f.write(hook)
        f.flush()

        proc = await Popen(
            shebang + [f.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, **env),
        )
        future = asyncio.ensure_future(_run_script_check(job, proc, script_name))
        await proc.wait()
        await asyncio.wait_for(future, None)
        if proc.returncode != 0:
            raise CallError(f"{script_name} failed with exit code {proc.returncode}")


async def _run_script_check(job, proc, name):
    while True:
        read = await proc.stdout.readline()
        if read == b"":
            break
        await job.logs_fd_write(f"[{name}] ".encode("utf-8") + read)
