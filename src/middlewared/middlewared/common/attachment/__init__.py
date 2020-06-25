from middlewared.service import ServiceChangeMixin
from middlewared.utils.path import is_child


class FSAttachmentDelegate(ServiceChangeMixin):
    """
    Represents something (share, automatic task, etc.) that needs to be enabled or disabled when dataset
    becomes available or unavailable (due to import/export, encryption/decryption, etc.)
    """

    # Unique identifier among all FSAttachmentDelegate classes
    name = NotImplementedError
    # Human-readable name of item handled by this delegate (e.g. "NFS Share")
    title = NotImplementedError
    # If is not None, corresponding service will be restarted after performing tasks on item
    service = None
    # attribute which is used to identify human readable description of an attachment
    resource_name = 'name'

    def __init__(self, middleware):
        self.middleware = middleware

    async def query(self, path, enabled, options=None):
        """
        Lists enabled/disabled items that depend on a dataset
        :param path: mountpoint of the dataset (e.g. "/mnt/tank/work")
        :param enabled: whether to list enabled or disabled items
        :param options: an optional attribute which can control the filters/logic applied to retrieve attachments
        :return: list of items of arbitrary type (will be passed to other methods of this class)
        """
        raise NotImplementedError

    async def get_attachment_name(self, attachment):
        """
        Returns human-readable description of item (e.g. it's path). Will be combined with `cls.title`.
        I.e. if you return here `/mnt/tank/work`, user will see: `NFS Share "/mnt/tank/work"`
        :param attachment: one of the items returned by `query`
        :return: string described above
        """
        return attachment[self.resource_name]

    async def delete(self, attachments):
        """
        Permanently delete said items
        :param attachments: list of the items returned by `query`
        :return: None
        """
        raise NotImplementedError

    async def toggle(self, attachments, enabled):
        """
        Enable or disable said items
        :param attachments: list of the items returned by `query`
        :param enabled:
        :return:
        """
        raise NotImplementedError

    async def detach(self, attachments):
        pass

    async def start(self, attachments):
        pass


class LockableFSAttachmentDelegate(FSAttachmentDelegate):
    """
    Represents a share/task/resource which is affected if the dataset underlying is locked
    """

    # service object
    service_class = NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled_field = self.service_class.enabled_field
        self.locked_field = self.service_class.locked_field
        self.path_field = self.service_class.path_field
        self.datastore_model = self.service_class._config.datastore
        self.datastore_prefix = self.service_class._config.datastore_prefix
        self.namespace = self.service_class._config.namespace
        if not self.service:
            self.service = self.service_class._config.service

    async def get_query_filters(self, enabled, options=None):
        options = options or {}
        filters = [[self.enabled_field, '=', enabled]]
        if 'locked' in options:
            filters += [[self.locked_field, '=', options['locked']]]
        return filters

    async def query(self, path, enabled, options=None):
        results = []
        for resource in await self.middleware.call(
            f'{self.namespace}.query', await self.get_query_filters(enabled, options)
        ):
            if await self.is_child_of_path(resource, path):
                results.append(resource)
        return results

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.toggle_enabled_for_attachment(attachment, enabled)
            await self.post_toggle_attachment(attachment, enabled)

        await self.post_toggle(attachments, enabled)

    async def toggle_enabled_for_attachment(self, attachment, enabled):
        await self.middleware.call(
            'datastore.update', self.datastore_model, attachment['id'], {
                f'{self.datastore_prefix}{self.enabled_field}': enabled
            }
        )

    async def post_toggle_attachment(self, attachment, enabled):
        if enabled:
            await self.remove_alert(attachment)

    async def post_toggle(self, attachments, enabled):
        """
        Child classes can override this to perform tasks after toggling of certain shares/resources
        """
        if enabled:
            await self.start(attachments)
        else:
            await self.stop(attachments)

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', self.datastore_model, attachment['id'])
            await self.post_delete_attachment(attachment)
        await self.post_delete(attachments)

    async def post_delete_attachment(self, attachment):
        await self.remove_alert(attachment)

    async def post_delete(self, attachments=None):
        """
        Child classes can override this to perform tasks after deletion of certain shares i.e restart services
        """
        await self.stop(attachments)

    async def detach(self, attachments):
        """
        Removes the attachment from it's configured service while keeping attachment enabled
        """
        try:
            for attachment in attachments:
                await self.toggle_enabled_for_attachment(attachment, False)
            await self.stop(attachments)
            for attachment in attachments:
                await self.middleware.call(f'{self.namespace}.generate_locked_alert', attachment['id'])
        finally:
            for attachment in attachments:
                await self.toggle_enabled_for_attachment(attachment, True)

    async def restart_reload_services(self, attachments):
        """
        Common method for post delete/toggle which child classes can use to restart/reload services
        """
        raise NotImplementedError

    async def remove_alert(self, attachment):
        await self.middleware.call(f'{self.namespace}.remove_locked_alert', attachment['id'])

    async def is_child_of_path(self, resource, path):
        return is_child(resource[self.path_field], path)

    async def start(self, attachments):
        for attachment in attachments:
            await self.remove_alert(attachment)
        await self.restart_reload_services(attachments)

    async def stop(self, attachments):
        await self.restart_reload_services(attachments)
