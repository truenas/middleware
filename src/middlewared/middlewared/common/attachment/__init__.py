from middlewared.service import ServiceChangeMixin


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
        self.logger = middleware.logger

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

    async def start(self, attachments):
        pass

    async def stop(self, attachments, options: dict | None = None):
        pass

    async def disable(self, attachments):
        """
        Disable said items, this is used when we export pool but do not want to delete
        related attachments
        :param attachments: list of the items returned by `query`
        :return: None
        """
        await self.toggle(attachments, False)


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

    async def start_service(self):
        if not (
            service_obj := await self.middleware.call('service.query', [['service', '=', self.service]])
        ) or not service_obj[0]['enable'] or service_obj[0]['state'] == 'RUNNING':
            return

        await (await self.middleware.call('service.control', 'START', self.service)).wait(raise_error=True)

    async def query(self, path, enabled, options=None):
        results = []
        options = options or {}
        check_parent = options.get('check_parent', False)
        exact_match = options.get('exact_match', False)
        for resource in await self.middleware.call(
            f'{self.namespace}.query', await self.get_query_filters(enabled, options)
        ):
            if await self.is_child_of_path(resource, path, check_parent, exact_match):
                results.append(resource)
        return results

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call(
                'datastore.update', self.datastore_model, attachment['id'], {
                    f'{self.datastore_prefix}{self.enabled_field}': enabled
                }
            )
            await self.remove_alert(attachment)

        if enabled:
            await self.start(attachments)
        else:
            await self.stop(attachments)

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', self.datastore_model, attachment['id'])
            await self.remove_alert(attachment)
        if attachments:
            await self.restart_reload_services(attachments)

    async def restart_reload_services(self, attachments):
        """
        Common method for post delete/toggle which child classes can use to restart/reload services
        """
        raise NotImplementedError

    async def remove_alert(self, attachment):
        await self.middleware.call(f'{self.namespace}.remove_locked_alert', attachment['id'])

    async def generate_alert(self, attachment):
        await self.middleware.call(f'{self.namespace}.generate_locked_alert', attachment['id'])

    async def is_child_of_path(self, resource, path, check_parent, exact_match):
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

        share_path = await self.service_class.get_path_field(self.service_class, resource)
        if exact_match or share_path == path:
            return share_path == path

        is_child = await self.middleware.call('filesystem.is_child', share_path, path)
        if not is_child and check_parent:
            return await self.middleware.call('filesystem.is_child', path, share_path)
        else:
            return is_child

    async def start(self, attachments):
        await self.start_service()
        for attachment in attachments:
            await self.remove_alert(attachment)
        if attachments:
            await self.restart_reload_services(attachments)

    async def stop(self, attachments, options=None):
        if attachments:
            await self.restart_reload_services(attachments)

        options = options or {}
        if options.get('locked'):
            if await self.check_service_for_alert_generation():
                # Let's generate alerts after service has been restarted/reloaded
                for attachment in attachments:
                    await self.generate_alert(attachment)

    async def check_service_for_alert_generation(self):
        if self.service:
            service_obj = await self.middleware.call('service.query', [['service', '=', self.service]])
            if not service_obj or service_obj[0]['state'] != 'RUNNING':
                # Service is not running, don't generate alerts
                return False

        return True
