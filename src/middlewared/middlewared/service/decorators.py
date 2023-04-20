import asyncio
import threading

from collections import defaultdict, namedtuple
from functools import wraps

from middlewared.schema import accepts, Int, List, OROperator, Ref, returns


LOCKS = defaultdict(asyncio.Lock)
PeriodicTaskDescriptor = namedtuple('PeriodicTaskDescriptor', ['interval', 'run_on_start'])
THREADING_LOCKS = defaultdict(threading.Lock)


def cli_private(fn):
    """Do not expose method in CLI"""
    fn._cli_private = True
    return fn


def filterable(fn):
    fn._filterable = True
    if hasattr(fn, 'wraps'):
        fn.wraps._filterable = True
    return accepts(Ref('query-filters'), Ref('query-options'))(fn)


def filterable_returns(schema):
    def filterable_internal(fn):
        operator = OROperator(
            Int('count'),
            schema,
            List('query_result', items=[schema.copy()]),
            name='filterable_result',
        )
        fn._filterable_schema = operator
        if hasattr(fn, 'wraps'):
            fn.wraps._filterable_schema = operator
        return returns(operator)(fn)
    return filterable_internal


def item_method(fn):
    """Flag method as an item method.
    That means it operates over a single item in the collection,
    by an unique identifier."""
    fn._item_method = True
    return fn


def job(
    lock=None, lock_queue_size=None, logs=False, process=False, pipes=None, check_pipes=True, transient=False,
    description=None, abortable=False
):
    """
    Flag method as a long running job. This must be the first decorator to be applied (meaning that it must be specified
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

        Please beware that, as `@job` decorator must be executed before `@accepts`, the arguments passed to the lock
        callable will be the raw arguments given by caller (there would be no arguments sanitizing or added defaults).

        Default value is `None` meaning that no locking is used.

    :param lock_queue_size: How many jobs with this lock can be in the `WAITING` state. For example, there is no sense
        to queue the same cloud sync or pool scrub twice so we specify `lock_queue_size=1`. The first called cloud sync
        will run normally; then, if we call a second cloudsync with the same id while the first is still running, it
        will be queued; and then, if we call a third cloudsync, it won't be queued anymore.

        If lock queue size is exceeded then the new job is discarded and the `id` of the last job in the queue is
        returned.

        Default value is `None` meaning that lock queue is infinite.

    :param logs: If `True` then `job.logs_fd` object will be available. It is an unbuffered file opened in binary mode;
        the job can write it's logs there and they will be available in the `/var/log/jobs/{id}.log` file. By default
        no such file is opened.

    :param process: If `True` then the job body is called in a separate process. By default, job body is executed in the
        main middleware process.

    :param pipes: A list of pipes a job can have. A job can have `pipes=["input"]` pipe, `pipes=["output"]` pipe
        or both at the same time.

        Pipes allow us to pass streaming data to/from a job. Job can read its input pipe via `job.pipes.input.r` and
        write to its output pipe via `job.pipes.output.w`. Both are binary mode streams. By default, no pipes are
        opened.

    :param check_pipes: If `True`, then the job will check that all its specified pipes are opened (it's the caller's
        responsibility to open the pipes). If `False`, then the job must explicitly run `job.check_pipe("input")`
        before accessing the pipe. This is useful when a job might or might need a pipe depending on its call arguemnts.
        By default, all pipes are checked.

    :param transient: If `True` then `"core.get_jobs"` ADDED or CHANGED event won't be sent for this job and it will
        be removed from `core.get_jobs` upon completion. This is useful for periodic service jobs that we don't want
        to see in task manager UI. By default the job is not transient.

    :param description: A callable that will return the job's human-readable description (that will appear in the task
        manager UI) based on its passed arguments. For example:

        .. code-block:: python

                @job(description=lambda dev, mode, *args: f'Wipe disk {dev}')

        Please beware that, as `@job` decorator must be executed before `@accepts`, the arguments passed to the
        description callable will be the raw arguments given by caller (there would be no arguments sanitizing or added
        defaults).

    :param abortable: If `True` then the job can be aborted in the task manager UI. When the job is aborted,
        `asyncio.CancelledError` is raised inside the job method (meaning that only asynchronous job methods can be
        aborted). By default, jobs are not abortable.
    """
    def check_job(fn):
        fn._job = {
            'lock': lock,
            'lock_queue_size': lock_queue_size,
            'logs': logs,
            'process': process,
            'pipes': pipes or [],
            'check_pipes': check_pipes,
            'transient': transient,
            'description': description,
            'abortable': abortable,
        }
        return fn
    return check_job


def lock(lock_str):
    def lock_fn(fn):
        if asyncio.iscoroutinefunction(fn):
            f_lock = LOCKS[lock_str]

            @wraps(fn)
            async def l_fn(*args, **kwargs):
                async with f_lock:
                    return await fn(*args, **kwargs)
        else:
            f_lock = THREADING_LOCKS[lock_str]

            @wraps(fn)
            def l_fn(*args, **kwargs):
                with f_lock:
                    return fn(*args, **kwargs)

        return l_fn

    return lock_fn


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def pass_app(*, require=False, rest=False):
    """Pass the application instance as parameter to the method."""
    def wrapper(fn):
        fn._pass_app = {
            'require': require,
            'rest': rest,
        }
        return fn
    return wrapper


def periodic(interval, run_on_start=True):
    def wrapper(fn):
        fn._periodic = PeriodicTaskDescriptor(interval, run_on_start)
        return fn

    return wrapper


def private(fn):
    """Do not expose method in public API"""
    fn._private = True
    return fn


def rest_api_metadata(extra_methods=None):
    """
    Allow having endpoints specify explicit rest methods.

    Explicit methods should be a list which specifies what methods the function should be available
    at other then the default one it is already going to be. This is useful when we want to maintain
    backwards compatibility with endpoints which were not expecting payload before but are now and users
    still would like to consume them with previous method which would be GET whereas it's POST now.
    """
    def wrapper(fn):
        fn._rest_api_metadata = {
            'extra_methods': extra_methods,
        }
        return fn
    return wrapper


def skip_arg(count=0):
    """Skip "count" arguments when validating accepts"""
    def wrap(fn):
        fn._skip_arg = count
        return fn
    return wrap


def threaded(pool):
    def m(fn):
        fn._thread_pool = pool
        return fn
    return m
