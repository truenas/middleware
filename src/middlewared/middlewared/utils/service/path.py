from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.service_exception import CallError, ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


async def check_path_service_write_allowed(
    verrors: ValidationErrors,
    middleware: Middleware,
    schema_name: str,
    path: str,
    dataset: str | None = None,
    relative_path: str | None = None,
    *,
    beneath: bool,
) -> None:
    """Refuse a path whose writes belong to another service.

    Not a permissions check: the path is refused whatever its mode. An S3 bucket's dataset is such a path: only
    the S3 service may write it.

    `dataset` and `relative_path` are the path as the kernel resolved it, which callers holding the pair
    pass so that a symlink or a bind mount cannot disguise where the path lands.

    With `beneath`, a path above such a dataset is refused too. Pass it for writers whose writes cross into child
    mounts.
    """
    await middleware.call2(
        middleware.services.sharing.s3.validate_writable_path,
        verrors,
        schema_name,
        path,
        dataset,
        relative_path,
        beneath=beneath,
    )


def require_path_service_write_allowed(middleware: Middleware, schema_name: str, path: str, *, beneath: bool) -> None:
    """`check_path_service_write_allowed` for a worker thread, raising what it refuses."""
    verrors = ValidationErrors()
    middleware.run_coroutine(check_path_service_write_allowed(verrors, middleware, schema_name, path, beneath=beneath))
    verrors.check()


def require_task_path_writable(middleware: Middleware, path: str) -> None:
    """Raise if a task would write `path` on or above another service's dataset. Checked at run time because a
    disabled task is not checked when it is saved or when a bucket is created, yet it can still be run."""
    verrors = ValidationErrors()
    middleware.run_coroutine(check_path_service_write_allowed(verrors, middleware, "path", path, beneath=True))
    if verrors:
        raise CallError(f"{verrors.errors[0].errmsg} Nothing was written.", errno.EPERM)


async def check_path_service_share_allowed(
    verrors: ValidationErrors,
    middleware: Middleware,
    schema_name: str,
    path: str,
    dataset: str | None = None,
    relative_path: str | None = None,
) -> None:
    """Refuse a path holding another service's private state to a share, which would hand that state to
    every client it reaches.

    Only what the service keeps for clients may be served: on an S3 bucket's dataset the `s3data`
    directory, which holds the objects, and nothing else.

    A task that copies the path is not asked this -- what it copies goes to the administrator, who may read
    the whole dataset. `dataset` and `relative_path` are as `check_path_service_write_allowed` takes them.
    """
    await middleware.call2(
        middleware.services.sharing.s3.validate_objects_path, verrors, schema_name, path, dataset, relative_path
    )
