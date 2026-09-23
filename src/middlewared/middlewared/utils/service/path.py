from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.service_exception import ValidationErrors


async def check_path_service_write_allowed(
    verrors: ValidationErrors,
    middleware: Middleware,
    schema_name: str,
    path: str,
    dataset: str | None = None,
    relative_path: str | None = None,
) -> None:
    """Refuse a path whose writes belong to another service.

    Not a permissions check: the path is refused however its mode reads, because what the service records
    about the writes it makes is not something a write from outside reaches. An S3 bucket's dataset is the
    one such path today -- a bucket's versioning, object lock and audit are the S3 service's, and a write
    from beside it bypasses all three.

    `dataset` and `relative_path` are the path as the kernel resolved it, which callers holding the pair
    pass so that a symlink or a bind mount cannot disguise where the path lands.
    """
    await middleware.call2(
        middleware.services.sharing.s3.validate_writable_path, verrors, schema_name, path, dataset, relative_path
    )


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
