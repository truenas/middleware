import shutil
import subprocess
import textwrap

from middlewared.service import CallError

CLONE_TIMEOUT = 900
PULL_TIMEOUT = 600
RESET_TIMEOUT = 120
CHECKOUT_TIMEOUT = 120
STATUS_TIMEOUT = 30


def clone_repository(
    repository_uri: str, destination: str, branch: str | None = None, depth: int | None = None
) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    args: list[str] = []
    for arg, var in filter(
        lambda e: e[1] is not None, (
            (['--branch', branch], branch),
            (['--depth', str(depth)], depth),
        )
    ):
        args.extend(arg)  # type: ignore[arg-type]

    try:
        cp = subprocess.run(
            ['git', 'clone'] + args + [repository_uri, destination], capture_output=True, timeout=CLONE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise CallError(
            f'Timed out after {CLONE_TIMEOUT} seconds cloning {repository_uri!r} repository '
            f'at {destination!r} destination'
        )

    if cp.returncode:
        error_message = textwrap.shorten(cp.stderr.decode(), width=50, placeholder='...')
        raise CallError(
            f'Failed to clone {repository_uri!r} repository at {destination!r} destination: {error_message}'
        )


def checkout_repository(destination: str, branch: str) -> None:
    try:
        cp = subprocess.run(
            ['git', '-C', destination, 'checkout', branch], capture_output=True, timeout=CHECKOUT_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise CallError(
            f'Timed out after {CHECKOUT_TIMEOUT} seconds checking out {branch!r} branch '
            f'for {destination!r} repository'
        )

    if cp.returncode:
        error_message = textwrap.shorten(cp.stderr.decode(), width=50, placeholder='...')
        raise CallError(
            f'Failed to checkout {branch!r} branch for {destination!r} repository: {error_message}'
        )


def update_repo(destination: str, branch: str) -> None:
    # Always reset to ensure working directory matches the repository state
    # This handles cases where files are missing, modified, or corrupted
    try:
        cp = subprocess.run(
            ['git', '-C', destination, 'reset', '--hard', f'origin/{branch}'],
            capture_output=True, timeout=RESET_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise CallError(f'Timed out after {RESET_TIMEOUT} seconds resetting {destination!r} repository')

    if cp.returncode:
        error_message = textwrap.shorten(cp.stderr.decode(), width=50, placeholder='...')
        raise CallError(
            f'Failed to reset {destination!r} repository: {error_message}'
        )

    try:
        cp = subprocess.run(
            ['git', '-C', destination, 'pull', 'origin', branch], capture_output=True, timeout=PULL_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise CallError(f'Timed out after {PULL_TIMEOUT} seconds updating {destination!r} repository')

    if cp.returncode:
        error_message = textwrap.shorten(cp.stderr.decode(), width=50, placeholder='...')
        raise CallError(
            f'Failed to update {destination!r} repository: {error_message}'
        )


def validate_git_repo(destination: str) -> bool:
    try:
        cp = subprocess.run(['git', '-C', destination, 'status'], capture_output=True, timeout=STATUS_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise CallError(f'Timed out after {STATUS_TIMEOUT} seconds reading status of {destination!r} repository')

    return cp.returncode == 0
