import os
import subprocess

from .args import parse
from .config import write_config
from .context import context_from_args
from .env import set_env
from .pytest_command import get_pytest_command


def run(workdir: str) -> None:
    ixautomation_dot_conf_url = (
        "https://raw.githubusercontent.com/iXsystems/ixautomation/master/src/etc/ixautomation.conf.dist"
    )
    config_file_msg = (
        f"Please add config.py to freenas/tests which can be empty or contain settings from {ixautomation_dot_conf_url}"
    )
    if not os.path.exists("config.py"):
        print(config_file_msg)
        exit(1)

    ctx = context_from_args(parse(), workdir)
    set_env(ctx)
    write_config(ctx)
    pytest_command = get_pytest_command(ctx)
    proc_returncode = subprocess.run(pytest_command).returncode
    if ctx.returncode:
        exit(proc_returncode)
