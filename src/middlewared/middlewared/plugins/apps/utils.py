import os
import subprocess
from typing import IO, Any, TypeVar, cast

from middlewared.api.base import BaseModel
from middlewared.api.current import AppEntry, AppUpgradeSummary
from middlewared.plugins.docker.state_utils import (
    IX_APPS_MOUNT_PATH as IX_APPS_MOUNT_PATH,
)
from middlewared.plugins.docker.state_utils import (  # noqa: F401,I250
    DatasetDefaults as DatasetDefaults,
)

from .ix_apps.utils import PROJECT_PREFIX as PROJECT_PREFIX  # noqa: F401,I250

T = TypeVar("T", bound=BaseModel)
UPGRADE_SNAP_PREFIX = "ix-app-upgrade-"


def to_entries(
    result: list[dict[str, Any]] | dict[str, Any] | int,
    model: type[T],
) -> list[T] | T | int:
    constructor = cast(type[T], getattr(model, "__query_result_item__", model))
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
        changelog="Image updates are available for this app",
        available_versions_for_upgrade=[],
    )


def get_upgrade_snap_name(app_name: str, app_version: str) -> str:
    return f"{UPGRADE_SNAP_PREFIX}{app_name}-{app_version}"


def get_app_stop_cache_key(app_name: str) -> str:
    return f"app_stop_{app_name}"


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
        encoding="utf8", errors="ignore", env=env or dict(os.environ),
    )
    out = ""
    err: str = ""
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        err = "Timed out waiting for response"
        proc.returncode = -1

    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=out, stderr=err)
    if check and cp.returncode:
        raise subprocess.CalledProcessError(cp.returncode, cp.args, stderr=err)
    return cp
