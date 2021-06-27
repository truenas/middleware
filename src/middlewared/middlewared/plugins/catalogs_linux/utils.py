import contextlib
import git
import logging
import os
import shutil
import threading

from collections import defaultdict
from git.exc import GitCommandError

from middlewared.service import CallError


GIT_LOCK = defaultdict(threading.Lock)
logger = logging.getLogger('catalog_utils')


def convert_repository_to_path(git_repository_uri, branch):
    return git_repository_uri.split('://', 1)[-1].replace('/', '_').replace('.', '_') + f'_{branch}'


def clone_repository(repository_uri, destination, depth):
    shutil.rmtree(destination, ignore_errors=True)
    return git.Repo.clone_from(repository_uri, destination, env=os.environ.copy(), depth=depth)


def get_repo(destination):
    with contextlib.suppress(git.InvalidGitRepositoryError, git.NoSuchPathError):
        return git.Repo(destination)


def pull_clone_repository(repository_uri, parent_dir, branch, depth=None, raise_exception=False):
    with GIT_LOCK[repository_uri]:
        os.makedirs(parent_dir, exist_ok=True)
        destination = os.path.join(parent_dir, convert_repository_to_path(repository_uri, branch))
        repo = get_repo(destination)
        clone_repo = not bool(repo)
        if repo:
            # We will try to checkout branch and do a git pull, if any of these operations fail, we will
            # clone the repository again. Why they might fail is if user has been manually playing with the repo
            try:
                repo.git.checkout(branch)
                repo.git.pull()
            except GitCommandError as e:
                logger.error('Failed to checkout branch / pull %r repository: %s', repository_uri, e)
                clone_repo = True

        if clone_repo:
            try:
                repo = clone_repository(repository_uri, destination, depth)
            except GitCommandError as e:
                msg = f'Failed to clone {repository_uri!r} repository at {destination!r} destination: {e}'
                logger.error(msg)
                if raise_exception:
                    raise CallError(msg)

                return False
            else:
                try:
                    repo.git.checkout(branch)
                except GitCommandError as e:
                    msg = f'Failed to checkout {branch!r} branch for {repository_uri!r} repository: {e}'
                    logger.error(msg)
                    if raise_exception:
                        raise CallError(msg)

                    return False

        return True


def get_cache_key(label, retrieve_versions):
    suffix = '' if retrieve_versions else '_without_versions'
    return f'catalog_{label}_train_details{suffix}'
