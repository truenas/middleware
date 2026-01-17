import asyncio
from collections import defaultdict, namedtuple
import threading
from typing import Callable, Concatenate, Literal, Sequence

from middlewared.api import API_LOADING_FORBIDDEN, api_method
from middlewared.api.base import BaseModel, query_result
if not API_LOADING_FORBIDDEN:
    from middlewared.api.current import QueryArgs, GenericQueryResult


LOCKS = defaultdict(asyncio.Lock)
PeriodicTaskDescriptor = namedtuple('PeriodicTaskDescriptor', ['interval', 'run_on_start'])
THREADING_LOCKS = defaultdict(threading.Lock)


def filterable_api_method(
    *,
    roles: list[str] | None = None,
    item: type[BaseModel] | None = None,
    private: bool = False,
    cli_private: bool = False,
    authorization_required: bool = True,
    pass_app: bool = False,
    pass_app_require: bool = False,
    pass_thread_local_storage: bool = False,
):
    def filterable_internal(fn):
        register_models = []
        if item:
            name = item.__name__
            if name.endswith("Entry"):
                if fn.__name__ == "query":
                    name = name.removesuffix("Entry") + "QueryResult"
                else:
                    name = name.removesuffix("Entry") + "Result"
            elif name.endswith("Item"):
                name = name.removesuffix("Item") + "Result"
            else:
                raise RuntimeError(f"{item=!r} class name must end with `Entry` or `Item`")

            returns = query_result(item, name)
            if not private:
                register_models = [(returns, query_result, item.__name__)]
        else:
            if not private:
                raise ValueError('Public methods may not use GenericQueryResult.')

            returns = GenericQueryResult

        wrapped = api_method(
            QueryArgs, returns, private=private, roles=roles, cli_private=cli_private,
            authorization_required=authorization_required, pass_app=pass_app, pass_app_require=pass_app_require,
            pass_thread_local_storage=pass_thread_local_storage,
        )(fn)
        wrapped._register_models = register_models
        return wrapped

    return filterable_internal


def job[**P, R, X](
    lock: Callable[[Sequence], str] | str | None = None,
    lock_queue_size: int | None = 5,
    logs: bool = False,
    pipes: list[Literal["input", "output"]] | None = None,
    check_pipes: bool = True,
    transient: bool = False,
    description: Callable[..., str] | None = None,
    abortable: bool = False,
    read_roles: list[str] | None = None,
) -> Callable[[Callable[Concatenate[X, P], R]], Callable[P, R]]:
    """
    Flag method as a long-running job. This must be the first decorator to be applied (meaning that it must be specified
    the last).

    Methods wrapped with this decorator must accept :class:`middlewared.job.Job` object as their first argument.

    :param lock: Determines a lock for this job to use. Locks prevent duplicate jobs that do the same work or access
        a shared resource from running at the same time. First job that obtains a lock will execute normally,
        subsequent jobs will stay in the `WAITING` state until the first job completes.

        Lock namespace is global. That way, if the method `"disk.wipe"` obtains a lock `"disk:sdb"`, then the method
        `"disk.format"` will have to wait for the same lock `"disk:sdb"` to be released.

        `lock` can be a constant string (for example, `lock='boot_scrub'`) or a callable that will accept the job's
        arguments and produce a lock name, e.g.:

        .. code-block:: python

            @job(lock=lambda args: f'scrub:{args[0]}')
            def scrub(self, pool_name):

        Please beware that, as `@job` decorator must be executed before `@api_method`, the arguments passed to the lock
        callable will be the raw arguments given by caller (there would be no arguments sanitizing or added defaults).

        Default value is `None` meaning that no locking is used.

    :param lock_queue_size: How many jobs with this lock can be in the `WAITING` state. For example, there is no sense
        to queue the same cloud sync or pool scrub twice, so we specify `lock_queue_size=1`. The first called cloud sync
        will run normally; then, if we call a second cloudsync with the same id while the first is still running, it
        will be queued; and then, if we call a third cloudsync, it won't be queued anymore.

        If lock queue size is exceeded then the new job is discarded and the `id` of the last job in the queue is
        returned.

        If lock queue size is zero, then launching a job when another job with the same lock is running will raise an
        `EBUSY` error.

        Default value is `5`. `None` would mean that lock queue is infinite.

    :param logs: If `True` then `job.logs_fd` object will be available. It is an unbuffered file opened in binary mode;
        the job can write its logs there, and they will be available in the `/var/log/jobs/{id}.log` file. By default,
        no such file is opened.

    :param pipes: A list of pipes a job can have. A job can have `pipes=["input"]` pipe, `pipes=["output"]` pipe
        or both at the same time.

        Pipes allow us to pass streaming data to/from a job. Job can read its input pipe via `job.pipes.input.r` and
        write to its output pipe via `job.pipes.output.w`. Both are binary mode streams. By default, no pipes are
        opened.

    :param check_pipes: If `True`, then the job will check that all its specified pipes are opened (it's the caller's
        responsibility to open the pipes). If `False`, then the job must explicitly run `job.check_pipe("input")`
        before accessing the pipe. This is useful when a job may or may not need a pipe depending on its call arguments.
        By default, all pipes are checked.

    :param transient: If `True` then `"core.get_jobs"` ADDED or CHANGED event won't be sent for this job, and it will
        be removed from `core.get_jobs` upon completion. This is useful for periodic service jobs that we don't want
        to see in task manager UI. By default, the job is not transient.

    :param description: A callable that will return the job's human-readable description (that will appear in the task
        manager UI) based on its passed arguments. For example:

        .. code-block:: python

                @job(description=lambda dev, mode, *args: f'Wipe disk {dev}')

        Please beware that, as `@job` decorator must be executed before `@api_method`, the arguments passed to the
        description callable will be the raw arguments given by caller (there would be no arguments sanitizing or added
        defaults).

    :param abortable: If `True` then the job can be aborted in the task manager UI. When the job is aborted,
        `asyncio.CancelledError` is raised inside the job method (meaning that only asynchronous job methods can be
        aborted). By default, jobs are not abortable.

    :param read_roles: A list of roles that will allow a non-full-admin user to see this job in `core.get_jobs`
        and download its logs even if the job was launched by another user or by the system.

        By default, non-full-admin users already can see their own jobs and download their logs, so this only should
        be used when the job is launched externally (i.e., using crontab).
    """
    def check_job(fn):
        fn._job = {
            'lock': lock,
            'lock_queue_size': lock_queue_size,
            'logs': logs,
            'process': False,
            'pipes': pipes or [],
            'check_pipes': check_pipes,
            'transient': transient,
            'description': description,
            'abortable': abortable,
            'read_roles': read_roles or [],
        }
        return fn

    return check_job


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def no_authz_required(fn):
    """Authorization not required to use the given method."""
    fn._no_authz_required = True
    return fn


def pass_app(*, message_id: bool = False, require: bool = False):
    """
    Pass the application instance as a parameter to the method.

    The decorated method receives an `app` parameter providing access to the API call context, including
    authentication credentials (`app.authenticated_credentials`), session ID, connection origin, and whether
    this is a WebSocket connection. Useful for authorization checks, audit logging, and passing caller context
    to nested method calls.

    :param message_id: If `True`, also pass a `message_id` parameter that uniquely identifies this API call.
        Used in CRUD methods for tracking and audit trails.

    :param require: If `True`, the `app` parameter is guaranteed to be non-None. Methods with `require=True`
        will error if called without an app context (e.g., from internal calls). If `False`, the method must
        handle `app` being None. Use `require=True` when the method needs caller identity/permissions and is
        only called via the API. Use `require=False` when the method works with or without caller context.
    """
    def wrapper(fn):
        fn._pass_app = {
            'message_id': message_id,
            'require': require,
        }
        return fn
    return wrapper


def pass_thread_local_storage[**P, R, X](fn: Callable[Concatenate[X, P], R]) -> Callable[P, R]:
    """
    Pass a thread-local storage object as a parameter to the method.

    The decorated method receives a `tls` parameter containing thread-local state initialized for the current
    thread. Primarily used to provide thread-safe access to libzfs handles (`tls.lzh`) for ZFS operations,
    since libzfs handles cannot be safely shared across threads.

    The `tls` object is an instance of `threading.local()` that is initialized per-thread with resources like
    a libzfs handle. Methods that directly interact with ZFS (create/destroy datasets, query properties, etc.)
    should use this decorator to access `tls.lzh` for thread-safe ZFS operations.
    """
    fn._pass_thread_local_storage = True
    return fn


def periodic(interval: float, run_on_start: bool = True):
    """
    Flag method as a periodic task that runs automatically at regular intervals.

    Periodic tasks are set up during middleware startup (when system state reaches 'READY') and run continuously
    throughout the middleware lifecycle. They are useful for maintenance operations, cache cleanup, health checks,
    and other recurring background tasks.

    :param interval: The number of seconds to wait between successive executions of the task. After the task
        completes (successfully or with an exception), the middleware will schedule the next execution to run after
        this many seconds. For example:

        .. code-block:: python

            @periodic(interval=3600)  # Run every hour
            async def cleanup_cache(self):
                ...

            @periodic(interval=86400)  # Run every 24 hours
            async def daily_maintenance(self):
                ...

        Common intervals:
        - 60 seconds = 1 minute
        - 3600 seconds = 1 hour
        - 86400 seconds = 24 hours

    :param run_on_start: If `True`, the task will execute immediately when middleware starts (with zero delay),
        and then again after the first `interval` passes. If `False`, the task will wait for the full `interval`
        duration before its first execution. Default is `True`.

        Use `run_on_start=True` when you want the task to run as soon as the system is ready, for example:

        .. code-block:: python

            @periodic(interval=86400)  # Runs immediately, then every 24 hours
            async def sync_encryption_keys(self):
                ...

        Use `run_on_start=False` when you want to delay the first execution, for example to avoid running
        resource-intensive tasks during system startup:

        .. code-block:: python

            @periodic(interval=3600, run_on_start=False)  # Waits 1 hour, then runs every hour
            async def health_check(self):
                ...

    Notes:
        - Periodic tasks are resilient to exceptions; if a task raises an exception, it will be logged and the
          task will be rescheduled to run again after the next interval.
        - Periodic tasks run in the main middleware event loop; long-running or CPU-intensive operations should offload
          work to separate threads/processes.
        - The interval timing starts after the task completes, not from when it starts. If a task takes 10 seconds
          to run and has a 60-second interval, the next execution will occur 70 seconds after the previous start.
        - Periodic tasks are typically combined with `@private` decorator since they run automatically and are not
          meant to be called directly via the API.
    """
    def wrapper(fn):
        fn._periodic = PeriodicTaskDescriptor(interval, run_on_start)
        return fn

    return wrapper


def private[T](fn: T) -> T:
    """Do not expose method in public API"""
    fn._private = True
    return fn
