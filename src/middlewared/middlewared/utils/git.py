import logging
import shutil
import subprocess

from middlewared.service import CallError

logger = logging.getLogger('git')

CLONE_TIMEOUT = 900
PULL_TIMEOUT = 600
RESET_TIMEOUT = 120
CHECKOUT_TIMEOUT = 120
STATUS_TIMEOUT = 30


def _failure(cp: subprocess.CompletedProcess[bytes], what: str) -> CallError:
    stderr = cp.stderr.decode(errors='replace')
    logger.error('%s:\n%s', what, stderr[-8192:].strip() or '<no output>')

    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    # `fatal:` is not always last: reset on a bad ref ends with usage boilerplate.
    reason = next(
        (line for prefix in ('fatal:', 'error:') for line in reversed(lines) if line.startswith(prefix)),
        lines[-1] if lines else f'git exited with code {cp.returncode}',
    )
    return CallError(f'{what}: {reason}. See /var/log/git.log for full git output')


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
        raise _failure(cp, f'Failed to clone {repository_uri!r} repository at {destination!r} destination')


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
        raise _failure(cp, f'Failed to checkout {branch!r} branch for {destination!r} repository')


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
        raise _failure(cp, f'Failed to reset {destination!r} repository')

    try:
        cp = subprocess.run(
            ['git', '-C', destination, 'pull', 'origin', branch], capture_output=True, timeout=PULL_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise CallError(f'Timed out after {PULL_TIMEOUT} seconds updating {destination!r} repository')

    if cp.returncode:
        raise _failure(cp, f'Failed to update {destination!r} repository')


def validate_git_repo(destination: str) -> bool:
    try:
        cp = subprocess.run(['git', '-C', destination, 'status'], capture_output=True, timeout=STATUS_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Callers read a false here as "unusable, clone it again", which is the repair this state wants.
        # Raising instead would skip that repair and fail the caller outright.
        logger.warning(
            '%s: timed out after %d seconds reading repository status, treating it as unusable',
            destination, STATUS_TIMEOUT,
        )
        return False

    return cp.returncode == 0
