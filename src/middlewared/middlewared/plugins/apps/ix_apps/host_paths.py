from collections.abc import Generator
import contextlib
import os
from pathlib import PurePath
from typing import Any

from middlewared.api.current import AppEntry
from middlewared.plugins.docker.state_utils import IX_APPS_MOUNT_PATH

from .lifecycle import get_rendered_template_config_of_app


def compose_bind_sources(compose_config: dict[str, Any]) -> Generator[str]:
    """The host paths the compose file bind-mounts. They are the service volumes in the short (`/host:/container`) or
    the long syntax, and the top-level volumes that bind a host directory through `driver_opts`."""
    for service in (compose_config.get("services") or {}).values():
        for volume in service.get("volumes") or []:
            if isinstance(volume, dict):
                source = str(volume.get("source") or "")
            else:
                source = volume.split(":", 1)[0]
            if source.startswith("/"):
                yield source
    for volume in (compose_config.get("volumes") or {}).values():
        driver_opts = (volume or {}).get("driver_opts") or {}
        device = str(driver_opts.get("device") or "")
        if "bind" in str(driver_opts.get("o") or "").split(",") and device.startswith("/"):
            yield device


def get_host_paths(app: AppEntry) -> list[str]:
    """The pool paths the app bind-mounts, each once, leaving out its own storage under the apps dataset. They are
    the binds its rendered compose declares, which a stopped app keeps, and the ones its containers hold. Blocking:
    it reads the rendered templates."""
    sources = [volume.source for volume in app.active_workloads.volumes]
    if app.version is not None:
        with contextlib.suppress(FileNotFoundError):
            sources.extend(compose_bind_sources(get_rendered_template_config_of_app(app.name, app.version)))
    return list(
        dict.fromkeys(
            source
            for source in sources
            if source.startswith("/mnt/") and not PurePath(os.path.normpath(source)).is_relative_to(IX_APPS_MOUNT_PATH)
        )
    )
