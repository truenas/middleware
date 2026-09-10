from collections import defaultdict
import logging
import threading
import typing

from middlewared.service import CallError
from middlewared.utils.git import checkout_repository, clone_repository, update_repo, validate_git_repo

GIT_LOCK: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
logger = logging.getLogger('git')


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
                logger.warning('%s: refresh failed, re-cloning from %r', destination, repository_uri)
                clone_repo = True

        if clone_repo:
            clone_repository(repository_uri, destination, branch, depth)

        return True
