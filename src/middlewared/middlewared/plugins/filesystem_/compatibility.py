from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerFilesystemDevice,
    FilesystemCompatibilityCompatibilityWarningsArgs,
    FilesystemCompatibilityCompatibilityWarningsResult,
    FilesystemCompatibilityPathConsumer,
    QueryOptions,
)
from middlewared.plugins.apps.ix_apps.host_paths import get_host_paths
from middlewared.service import Service, ValidationErrors, private

if TYPE_CHECKING:
    from middlewared.main import Middleware

WORKLOADS = ("app", "container")

ResolvedConsumers = list[tuple[FilesystemCompatibilityPathConsumer, PurePath]]


def resolved(consumers: list[FilesystemCompatibilityPathConsumer]) -> ResolvedConsumers:
    """Blocking: it resolves every path."""
    return [(consumer, Path(consumer.path).resolve()) for consumer in consumers]


def overlapping(
    consumers: ResolvedConsumers, path: PurePath, service: str
) -> list[FilesystemCompatibilityPathConsumer]:
    """The consumers that conflict with `service` on the resolved `path`: those whose path is `path`, a parent of it
    or a child of it. A workload conflicts with everything but its own kind. Sharers never conflict with each other."""
    return [
        consumer
        for consumer, consumer_path in consumers
        if consumer.service != service
        and (consumer.service in WORKLOADS or service in WORKLOADS)
        and (consumer_path.is_relative_to(path) or path.is_relative_to(consumer_path))
    ]


def conflicts_on(
    consumers: list[FilesystemCompatibilityPathConsumer], paths: list[str], service: str
) -> dict[str, list[FilesystemCompatibilityPathConsumer]]:
    """Blocking: every path, once, with the consumers that conflict with `service` on it."""
    resolved_consumers = resolved(consumers)
    return {path: overlapping(resolved_consumers, Path(path).resolve(), service) for path in dict.fromkeys(paths)}


def conflicting_paths(
    consumers: list[FilesystemCompatibilityPathConsumer],
) -> dict[str, list[FilesystemCompatibilityPathConsumer]]:
    resolved_consumers = resolved(consumers)
    conflicts = {}
    for consumer, path in resolved_consumers:
        if consumer.service not in WORKLOADS or consumer.path in conflicts:
            continue
        if others := overlapping(resolved_consumers, path, consumer.service):
            conflicts[consumer.path] = sorted([consumer, *others], key=lambda c: (c.service, c.name, c.path))
    return conflicts


def describe(consumers: list[FilesystemCompatibilityPathConsumer], path: str) -> str:
    titles = {
        "sharing.smb": "SMB share",
        "sharing.nfs": "NFS share",
        "sharing.webshare": "Webshare",
        "sharing.s3": "S3 bucket",
        "cloudsync": "Cloud sync task",
        "rsynctask": "Rsync task",
        "app": "App",
        "container": "Container",
    }
    labels = []
    for consumer in consumers:
        label = f"{titles[consumer.service]} {consumer.name!r}"
        if consumer.path != path:
            label += f" ({consumer.path})"
        labels.append(label)
    return ", ".join(labels)


class FilesystemCompatibilityService(Service):
    class Config:
        namespace = "filesystem.compatibility"
        cli_private = True

    @private
    async def path_consumers(self) -> list[FilesystemCompatibilityPathConsumer]:
        """Every consumer with the host path it uses. A disabled share or task, or a task that only reads its path,
        is none."""
        options = QueryOptions(extra={"retrieve_locked_info": False})
        consumers = []
        for share in await self.middleware.call("sharing.smb.query", [["enabled", "=", True]], options.model_dump()):
            if share["path"].startswith("/"):
                consumers.append(
                    FilesystemCompatibilityPathConsumer(
                        service="sharing.smb", id=share["id"], name=share["name"], path=share["path"]
                    )
                )
        for share in await self.call2(self.s.sharing.nfs.query, [["enabled", "=", True]], options):
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="sharing.nfs", id=share.id, name=share.path, path=share.path
                )
            )
        for share in await self.call2(self.s.sharing.webshare.query, [["enabled", "=", True]], options):
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="sharing.webshare", id=share.id, name=share.name, path=share.path
                )
            )
        buckets = await self.call2(self.s.sharing.s3.query, [["enabled", "=", True]], options)
        assert isinstance(buckets, list)  # FIXME when S3 is converted to new-style
        for bucket in buckets:
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="sharing.s3", id=bucket.id, name=bucket.name, path=f"/mnt/{bucket.dataset}"
                )
            )
        for task in await self.call2(
            self.s.cloudsync.query, [["enabled", "=", True], ["direction", "=", "PULL"]], options
        ):
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="cloudsync", id=task.id, name=task.description or task.path, path=task.path
                )
            )
        for rsync in await self.call2(
            self.s.rsynctask.query, [["enabled", "=", True], ["direction", "=", "PULL"]], options
        ):
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="rsynctask", id=rsync.id, name=rsync.desc or rsync.path, path=rsync.path
                )
            )
        apps = await self.call2(self.s.app.query)
        for app, paths in await self.middleware.run_in_thread(lambda: [(app, get_host_paths(app)) for app in apps]):
            for path in paths:
                consumers.append(
                    FilesystemCompatibilityPathConsumer(service="app", id=app.name, name=app.name, path=path)
                )
        names = {container.id: container.name for container in await self.call2(self.s.container.query)}
        for device in await self.call2(self.s.container.device.query, [["attributes.dtype", "=", "FILESYSTEM"]]):
            assert isinstance(device.attributes, ContainerFilesystemDevice)
            consumers.append(
                FilesystemCompatibilityPathConsumer(
                    service="container",
                    id=device.container,
                    name=names[device.container],
                    path=device.attributes.source,
                )
            )
        return consumers

    @api_method(
        FilesystemCompatibilityCompatibilityWarningsArgs,
        FilesystemCompatibilityCompatibilityWarningsResult,
        roles=["READONLY_ADMIN"],
        check_annotations=True,
    )
    async def compatibility_warnings(self, path: str, service: str) -> list[FilesystemCompatibilityPathConsumer]:
        """
        The consumers that also use ``path`` and conflict with the consumer of ``service`` that wants to use it.
        A consumer uses ``path`` when its host path is ``path``, a parent of it or a child of it. An app or a container
        conflicts with everything but another of its own kind. Shares and tasks that write the path never conflict
        with each other.

        A file-sharing protocol, an app and a container are separate operating-system environments. Each one makes
        its own assumptions about locking, caching, permissions, ownership and application state. Giving two of them
        the same data breaks these assumptions. The API refuses to create or update such a consumer unless
        the caller sets ``force_path_conflicts``.
        """
        consumers = await self.path_consumers()
        return (await self.middleware.run_in_thread(conflicts_on, consumers, [path], service))[path]

    @private
    async def validate_path(self, verrors: ValidationErrors, path: str, service: str) -> None:
        await self.validate_paths(verrors, [path], service)

    @private
    async def validate_paths(self, verrors: ValidationErrors, paths: list[str], service: str) -> None:
        consumers = await self.path_consumers()
        conflicts = await self.middleware.run_in_thread(conflicts_on, consumers, paths, service)
        for path, conflicting in conflicts.items():
            if conflicting:
                verrors.add(
                    "options.force_path_conflicts",
                    f"{path} is also used by {describe(conflicting, path)}. Exposing the same data to another "
                    "operating-system environment can cause inconsistent data, application failures, permission "
                    "changes, or data corruption. Set `force_path_conflicts` to proceed anyway.",
                )

    @private
    async def conflicts(self) -> dict[str, str]:
        """Every path an app or a container uses that another consumer also uses, with all of its consumers
        described."""
        conflicts = await self.middleware.run_in_thread(conflicting_paths, await self.path_consumers())
        return {path: describe(consumers, path) for path, consumers in conflicts.items()}


async def clear_alert_source_run(middleware: Middleware, *args: Any, **kwargs: Any) -> None:
    await middleware.call2(middleware.services.alert.alert_source_clear_run, "PathUsedByMultipleServices")


async def setup(middleware: Middleware) -> None:
    # A changed consumer is checked by the next alert run instead of the daily one
    for namespace in (
        "sharing.smb",
        "sharing.nfs",
        "sharing.webshare",
        "sharing.s3",
        "cloudsync",
        "rsynctask",
        "app",
        "container",
        "container.device",
    ):
        for action in ("create", "update", "delete"):
            middleware.register_hook(f"{namespace}.post_{action}", clear_alert_source_run)
