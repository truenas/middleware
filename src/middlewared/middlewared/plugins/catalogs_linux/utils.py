import contextlib
import git
import logging
import os
import shutil
import threading

from collections import defaultdict
from git.exc import GitCommandError


GIT_LOCK = defaultdict(threading.Lock)
logger = logging.getLogger('catalog_utils')


def convert_repository_to_path(git_repository_uri):
    # Following is the logic which iocage uses to ensure unique directory names for each uri
    return git_repository_uri.split('://', 1)[-1].replace('/', '_').replace('.', '_')


def clone_repository(repository_uri, destination, depth):
    shutil.rmtree(destination, ignore_errors=True)
    kwargs = {'env': os.environ.copy(), 'depth': depth}
    return git.Repo.clone_from(repository_uri, destination, **{k: v for k, v in kwargs.items() if v})


def get_repo(destination):
    with contextlib.suppress(git.InvalidGitRepositoryError, git.NoSuchPathError):
        return git.Repo(destination)


def pull_clone_repository(repository_uri, parent_dir, branch, depth=None):
    with GIT_LOCK[repository_uri]:
        destination = os.path.join(parent_dir, convert_repository_to_path(repository_uri))
        repo = get_repo(destination)
        clone_repo = bool(repo)
        if repo:
            # We will try to checkout branch and do a git pull, if any of these operations fail, we will
            # clone the repository again. Why they might fail is if user has been manually playing with the repo
            try:
                for action, params in (('checkout', [branch]), ('pull', [])):
                    getattr(repo.git, action)(*params)
            except GitCommandError as e:
                logger.error('Failed to %r %r repository: %s', action, repository_uri, e)
                clone_repo = True

        if clone_repo:
            try:
                repo = clone_repository(repository_uri, destination, depth)
            except GitCommandError as e:
                logger.error('Failed to clone %r repository at %r destination: %r', repository_uri, destination, e)
                return False
            else:
                try:
                    repo.git.checkout(branch)
                except GitCommandError as e:
                    logger.error('Failed to checkout %r branch for %r repository: %s', branch, repository_uri, e)
                    return False

        return True
