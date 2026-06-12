from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Protocol

from middlewared.service import GenericSharingTaskService, ServiceChangeMixin, SharingTaskService

if TYPE_CHECKING:
    from middlewared.main import Middleware


class Entry(Protocol):
    id: int


class FSAttachmentDelegate[E](ServiceChangeMixin):
    """
    Represents something (share, automatic task, etc.) that needs to be enabled or disabled when dataset
    becomes available or unavailable (due to import/export, encryption/decryption, etc.)
    """

    # Unique identifier among all FSAttachmentDelegate classes
    name: str
    # Human-readable name of item handled by this delegate (e.g. "NFS Share")
    title: str
    # If is not None, corresponding service will be restarted after performing tasks on item
    service: str | None = None
    # attribute which is used to identify human readable description of an attachment
    resource_name = "name"
    # Priority for ordering delegate operations
    # On start: delegates are processed high-to-low priority (infrastructure starts first)
    # On stop: delegates are processed low-to-high priority (dependent services stop first)
    # Delegates with same priority maintain registration order among themselves.
    priority = 0

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware
        self.logger = middleware.logger

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[E]:
        """
        Lists enabled/disabled items that depend on a dataset
        :param path: mountpoint of the dataset (e.g. "/mnt/tank/work")
        :param enabled: whether to list enabled or disabled items
        :param options: an optional attribute which can control the filters/logic applied to retrieve attachments
        :return: list of items of arbitrary type (will be passed to other methods of this class)
        """
        raise NotImplementedError

    async def get_attachment_name(self, attachment: E) -> str:
        """
        Returns human-readable description of item (e.g. it's path). Will be combined with `cls.title`.
        I.e. if you return here `/mnt/tank/work`, user will see: `NFS Share "/mnt/tank/work"`
        :param attachment: one of the items returned by `query`
        :return: string described above
        """
        if isinstance(attachment, dict):
            # FIXME: This must be eventually removed
            return attachment[self.resource_name]  # type: ignore[no-any-return]
        else:
            return getattr(attachment, self.resource_name)  # type: ignore[no-any-return]

    async def delete(self, attachments: list[E]) -> None:
        """
        Permanently delete said items
        :param attachments: list of the items returned by `query`
        :return: None
        """
        raise NotImplementedError

    async def toggle(self, attachments: list[E], enabled: bool) -> None:
        """
        Enable or disable said items
        :param attachments: list of the items returned by `query`
        :param enabled:
        :return:
        """
        raise NotImplementedError

    async def start(self, attachments: list[E]) -> None:
        pass

    async def stop(self, attachments: list[E]) -> None:
        pass

    async def disable(self, attachments: list[E]) -> None:
        """
        Disable said items, this is used when we export pool but do not want to delete
        related attachments
        :param attachments: list of the items returned by `query`
        :return: None
        """
        await self.toggle(attachments, False)


class LockableFSAttachmentDelegate[E: Entry](FSAttachmentDelegate[E]):
    """
    Represents a share/task/resource which is affected if the dataset underlying is locked
    """

    # service object
    service_class: type[SharingTaskService[E]] | type[GenericSharingTaskService[E]]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.namespace = self.service_class._config.namespace  # type: ignore[attr-defined]
        if self.service_class._config.datastore:  # type: ignore[attr-defined]
            # Legacy SharingTaskService: field config + datastore live on the service class.
            svc = self.service_class
            self.enabled_field = svc.enabled_field  # type: ignore[union-attr]
            self.locked_field = svc.locked_field  # type: ignore[union-attr]
            self.path_field = svc.path_field  # type: ignore[union-attr]
            self.datastore_model = svc._config.datastore  # type: ignore[attr-defined]
            self.datastore_prefix = svc._config.datastore_prefix  # type: ignore[attr-defined]
            self._resource_path = functools.partial(svc.get_path_field, svc)  # type: ignore[union-attr,arg-type]
        else:
            # Typesafe GenericSharingTaskService: field config + datastore live on the service
            # part; read them off the running instance's part.
            part = self.middleware.get_service(self.namespace)._svc_part  # type: ignore[attr-defined]
            self.enabled_field = part.enabled_field
            self.locked_field = part.locked_field
            self.path_field = part.path_field
            self.datastore_model = part._datastore
            self.datastore_prefix = part._datastore_prefix
            self._resource_path = part.get_path_field
        if not self.service:
            self.service = self.service_class._config.service  # type: ignore[attr-defined]

    async def get_query_filters(self, enabled: bool, options: dict[str, Any] | None = None) -> list[Any]:
        options = options or {}
        filters = [[self.enabled_field, "=", enabled]]
        if "locked" in options:
            filters += [[self.locked_field, "=", options["locked"]]]
        return filters

    async def start_service(self) -> None:
        if (
            not (service_obj := await self.middleware.call("service.query", [["service", "=", self.service]]))
            or not service_obj[0]["enable"]
            or service_obj[0]["state"] == "RUNNING"
        ):
            return

        await (await self.middleware.call("service.control", "START", self.service)).wait(raise_error=True)

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[E]:
        results = []
        options = options or {}
        check_parent = options.get("check_parent", False)
        exact_match = options.get("exact_match", False)
        for resource in await self.middleware.call(
            f"{self.namespace}.query", await self.get_query_filters(enabled, options)
        ):
            if await self.is_child_of_path(resource, path, check_parent, exact_match):
                results.append(resource)
        return results

    async def toggle(self, attachments: list[E], enabled: bool) -> None:
        for attachment in attachments:
            if isinstance(attachment, dict):
                # FIXME: This must be eventually removed
                attachment_id = attachment["id"]
            else:
                attachment_id = attachment.id

            await self.middleware.call(
                "datastore.update",
                self.datastore_model,
                attachment_id,
                {f"{self.datastore_prefix}{self.enabled_field}": enabled},
            )
            await self.remove_alert(attachment)

        if enabled:
            await self.start(attachments)
        else:
            await self.stop(attachments)

    async def delete(self, attachments: list[E]) -> None:
        for attachment in attachments:
            if isinstance(attachment, dict):
                # FIXME: This must be eventually removed
                attachment_id = attachment["id"]
            else:
                attachment_id = attachment.id

            await self.middleware.call("datastore.delete", self.datastore_model, attachment_id)
            await self.remove_alert(attachment)
        if attachments:
            await self.restart_reload_services(attachments)

    async def restart_reload_services(self, attachments: list[E]) -> None:
        """
        Common method for post delete/toggle which child classes can use to restart/reload services
        """
        raise NotImplementedError

    async def remove_alert(self, attachment: E) -> None:
        if isinstance(attachment, dict):
            # FIXME: This must be eventually removed
            attachment_id = attachment["id"]
        else:
            attachment_id = attachment.id

        await self.middleware.call(f"{self.namespace}.remove_locked_alert", attachment_id)

    async def is_child_of_path(self, resource: E, path: str, check_parent: bool, exact_match: bool) -> bool:
        # What this is essentially doing is testing if resource in question is a child of queried path
        # and not vice versa. While this is desirable in most cases, there are cases we also want to see
        # if path is a child of the resource in question. In that case we want the following:
        # 1) When parent of configured path is specified we return true
        # 2) When configured path itself is specified we return true
        # 3) When path is child of configured path, we return true as the path
        #    is being consumed by service in question
        #
        # In most cases we want to cater to above child cases with resource path and the path specified
        # but there can also be cases when we just want to be sure if the resource path and the path to check
        # are equal and for that case `exact_match` is used where we do not try to see if one is the child of
        # another or vice versa. We just check if they are equal.
        #
        # `check_parent` flag when set can be used to check for the case when share path is the parent
        # of the path to check.

        share_path = await self._resource_path(resource)
        if exact_match or share_path == path:
            return share_path == path

        is_child = await self.middleware.call("filesystem.is_child", share_path, path)
        if not is_child and check_parent:
            return await self.middleware.call("filesystem.is_child", path, share_path)  # type: ignore[no-any-return]
        else:
            return is_child  # type: ignore[no-any-return]

    async def start(self, attachments: list[E]) -> None:
        await self.start_service()
        for attachment in attachments:
            await self.remove_alert(attachment)
        if attachments:
            await self.restart_reload_services(attachments)

    async def stop(self, attachments: list[E]) -> None:
        if attachments:
            await self.restart_reload_services(attachments)
