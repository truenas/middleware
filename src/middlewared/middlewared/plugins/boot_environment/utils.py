import subprocess

from middlewared.service_exception import CallError

__all__ = ("run_zectl_cmd",)


def run_zectl_cmd(cmd: list[str]) -> bool:
    try:
        cp = subprocess.run(
            ["zectl"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
    except subprocess.CalledProcessError as cpe:
        raise CallError(f"Unexpected error: {cpe.stdout.decode()!r}")
    else:
        return cp.returncode == 0
