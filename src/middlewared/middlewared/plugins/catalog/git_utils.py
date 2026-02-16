import logging
import threading
import typing
from collections import defaultdict

from middlewared.service import CallError
from middlewared.utils.git import clone_repository, checkout_repository, update_repo, validate_git_repo


GIT_LOCK: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
logger = logging.getLogger('catalog_utils')


def convert_repository_to_path(git_repository_uri: str, branch: str) -> str:
    return git_repository_uri.split('://', 1)[-1].replace('/', '_').replace('.', '_') + f'_{branch}'


def pull_clone_repository(repository_uri: str, destination: str, branch: str, depth: typing.Optional[int] = 1) -> bool:
    with GIT_LOCK[repository_uri]:
        valid_repo = validate_git_repo(destination)
        clone_repo = not bool(valid_repo)
        if valid_repo:
            # We will try to checkout branch and do a git pull, if any of these operations fail,
            # we will clone the repository again.
            # Why they might fail is if user has been manually playing with the repo or repo was force-pushed
            try:
                checkout_repository(destination, branch)
                update_repo(destination, branch)
            except CallError:
                clone_repo = True

        if clone_repo:
            try:
                clone_repository(repository_uri, destination, branch, depth)
            except CallError as e:
                raise CallError(f'Failed to clone {repository_uri!r} repository at {destination!r} destination: {e}')

        return True
