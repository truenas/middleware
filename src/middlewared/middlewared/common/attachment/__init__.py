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


class LockableFSAttachmentDelegate(FSAttachmentDelegate):
    """
    Represents a share/task/resource which is affected if the dataset underlying is locked
    """

    # service namespace
    namespace = NotImplementedError
    # enabled field
    enabled_field = NotImplementedError
    # locked field
    locked_field = NotImplementedError
    # path_field
    path_field = NotImplementedError
    # datastore model
    datastore_model = NotImplementedError

    async def get_query_filters(self, enabled, options=None):
        options = options or {}
        filters = [[self.enabled_field, '=', enabled]]
        if self.locked_field in options:
            filters += [[self.locked_field, '=', self.locked_field]]
        return filters

    async def is_child_of_path(self, resource, path):
        return is_child(resource[self.path_field], path)

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', self.datastore_model, attachment['id'])
            await self.post_delete_attachment(attachment)
        await self.post_delete()

    async def post_delete_attachment(self, attachment):
        await self.middleware.call(f'{self.namespace}.remove_locked_alert', attachment['id'])

    async def post_delete(self):
        """
        Child classes can override this to perform tasks after deletion of certain shares i.e restart services
        """

    async def query(self, path, enabled, options=None):
        results = []
        for resource in await self.middleware.call(
            f'{self.namespace}.query', await self.get_query_filters(enabled, options)
        ):
            if await self.is_child_of_path(resource, path):
                results.append(resource)
        return results
