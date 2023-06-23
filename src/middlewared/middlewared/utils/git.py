import subprocess
import shutil
import typing

from middlewared.service import CallError


def clone_repository(
    repository_uri: str, destination: str, branch: typing.Optional[str] = None, depth: typing.Optional[int] = None
) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    args = []
    for arg, var in filter(
        lambda e: e[1] is not None, (
            (['--branch', branch], branch),
            (['--depth', str(depth)], depth),
        )
    ):
        args.append(arg)

    cp = subprocess.run(['git', 'clone'] + args + [repository_uri, destination], capture_output=True)
    if cp.returncode:
        raise CallError(
            f'Failed to clone {repository_uri!r} repository at {destination!r} destination: {cp.stderr.decode()}'
        )
