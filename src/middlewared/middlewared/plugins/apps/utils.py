from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from typing import IO, TYPE_CHECKING, Any, Callable, TypeVar, cast

from middlewared.api.base import BaseModel
from middlewared.api.current import AppEntry, AppUpgradeSummary
from middlewared.plugins.docker.state_utils import (
    IX_APPS_MOUNT_PATH as IX_APPS_MOUNT_PATH,
)
from middlewared.plugins.docker.state_utils import (  # noqa: F401,I250
    DatasetDefaults as DatasetDefaults,
)

from .ix_apps.utils import PROJECT_PREFIX as PROJECT_PREFIX  # noqa: F401,I250

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.utils.types import JobProgressCallback

logger = logging.getLogger('app_lifecycle')

T = TypeVar('T', bound=BaseModel)
UPGRADE_SNAP_PREFIX = 'ix-app-upgrade-'


def to_entries(
    result: list[dict[str, Any]] | dict[str, Any] | int,
    model: type[T],
) -> list[T] | T | int:
    constructor = cast(type[T], getattr(model, '__query_result_item__', model))
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        return constructor(**result)
    return [constructor(**row) for row in result]


def upgrade_summary_info(app: AppEntry) -> AppUpgradeSummary:
    return AppUpgradeSummary(
        latest_version=app.version,
        latest_human_version=app.human_version,
        upgrade_version=app.version,
        upgrade_human_version=app.human_version,
        changelog='Image updates are available for this app',
        available_versions_for_upgrade=[],
    )


def get_upgrade_snap_name(app_name: str, app_version: str) -> str:
    return f'{UPGRADE_SNAP_PREFIX}{app_name}-{app_version}'


def get_app_stop_cache_key(app_name: str) -> str:
    return f'app_stop_{app_name}'


def run(
    args: list[str],
    *,
    stdout: int | IO[Any] = subprocess.PIPE,
    stderr: int | IO[Any] = subprocess.PIPE,
    timeout: int = 60,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        args, stdout=stdout, stderr=stderr,
        encoding='utf8', errors='ignore', env=env or dict(os.environ),
    )
    out = ''
    err: str = ''
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        err = 'Timed out waiting for response'
        proc.returncode = -1

    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=out, stderr=err)
    if check and cp.returncode:
        raise subprocess.CalledProcessError(cp.returncode, cp.args, stderr=err)
    return cp


def run_streaming(
    args: list[str],
    *,
    line_callback: Callable[[str], None],
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Like `run`, but invokes `line_callback` with each line of stderr as it is produced
    instead of buffering output until the process exits.
    """
    # Run in its own session so the timeout can signal the whole process group. `docker compose`
    # spawns the compose plugin as a child, and killing only the direct process would orphan it,
    # leaving it holding the stderr pipe open and blocking the readline loop below past the timeout.
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='utf8', errors='ignore', env=env or dict(os.environ), start_new_session=True,
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    timed_out = False

    def drain_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout_lines.append(line)

    def kill_process_group() -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    def on_timeout() -> None:
        nonlocal timed_out
        if proc.poll() is None:
            # Written here before the kill and read in the finally block below. The kill is what
            # ends the readline loop (EOF), which happens-before that read, so no lock is needed.
            timed_out = True
            kill_process_group()

    drain_thread = threading.Thread(target=drain_stdout, daemon=True)
    drain_thread.start()
    timer = threading.Timer(timeout, on_timeout)
    timer.start()
    callback_usable = True
    try:
        assert proc.stderr is not None
        # iter(readline) instead of direct file iteration: the latter's read-ahead buffering
        # would deliver lines in large batches, defeating real-time streaming
        for line in iter(proc.stderr.readline, ''):
            stderr_lines.append(line)
            if callback_usable:
                try:
                    line_callback(line)
                except Exception:
                    logger.warning('%r: line callback failed, output streaming disabled', args[0], exc_info=True)
                    callback_usable = False
    finally:
        timer.cancel()
        # Reap in finally so an unexpected error in the read loop cannot leave the child (and its
        # process group) running; kill first if it somehow outlived the loop without timing out.
        if proc.poll() is None:
            kill_process_group()
        proc.wait()
        drain_thread.join(timeout=10)

    if timed_out:
        return subprocess.CompletedProcess(args, -1, stdout='', stderr='Timed out waiting for response')

    return subprocess.CompletedProcess(
        args, proc.returncode, stdout=''.join(stdout_lines), stderr=''.join(stderr_lines),
    )


def band_progress(job: Job, start: float, end: float) -> Callable[[float, str], None]:
    """
    Return a callback mapping a 0.0-1.0 completion fraction of a sub-operation into
    `job` progress within the [start, end] band.
    """
    def callback(fraction: float, description: str) -> None:
        job.set_progress(start + (end - start) * min(max(fraction, 0.0), 1.0), description)

    return callback


def child_job_progress(job: Job, start: float, end: float, description_prefix: str = '') -> JobProgressCallback:
    """
    Return a `job_on_progress_cb` callback for `call2`/`call_sync2` that maps a child
    job's 0-100 progress into `job` progress within the [start, end] band.
    """
    def callback(encoded: dict[str, Any]) -> None:
        progress = encoded['progress']
        percent = min(max(progress['percent'] or 0, 0), 100)
        job.set_progress(
            start + (end - start) * (percent / 100),
            f'{description_prefix}{progress["description"] or ""}',
        )

    return callback
