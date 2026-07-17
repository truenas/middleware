import subprocess

from .args import parse
from .artifacts import get_artifacts
from .config import write_config
from .context import context_from_args
from .env import set_env
from .pytest_command import get_pytest_command


def run(workdir: str) -> None:
    ctx = context_from_args(parse(), workdir)
    set_env(ctx)
    write_config(ctx)
    pytest_command = get_pytest_command(ctx)
    proc_returncode = subprocess.run(pytest_command).returncode
    get_artifacts(ctx)
    if ctx.returncode:
        exit(proc_returncode)
