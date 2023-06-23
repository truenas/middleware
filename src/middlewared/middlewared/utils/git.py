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


def checkout_repository(destination: str, branch: str) -> None:
    cp = subprocess.run(['git', '-C', destination, 'checkout', branch], capture_output=True)
    if cp.returncode:
        raise CallError(
            f'Failed to checkout {branch!r} branch for {destination!r} repository: {cp.stderr.decode()}'
        )


def update_repo(destination: str, branch: str) -> None:
    cp = subprocess.run(['git', '-C', destination, 'pull', 'origin', branch], capture_output=True)
    if cp.returncode:
        raise CallError(
            f'Failed to update {destination!r} repository: {cp.stderr.decode()}'
        )


def validate_git_repo(destination: str) -> bool:
    cp = subprocess.run(['git', '-C', destination, 'status'], capture_output=False)
    return cp.returncode == 0
