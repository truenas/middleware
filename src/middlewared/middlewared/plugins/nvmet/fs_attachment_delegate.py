import os

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.nvmet.namespace import NVMetNamespaceService
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name


class NVMetNamespaceAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'nvmet'
    title = 'NVMe-oF Namespace'
    service = 'nvmet'
    service_class = NVMetNamespaceService
    resource_name = 'device_path'
    set_triggers = frozenset({'volsize', 'snapdev'})

    async def restart_reload_services(self, attachments):
        await self.middleware.call('nvmet.global.reload')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'start' if enabled else 'stop'
            try:
                await self.middleware.call(f'nvmet.namespace.{action}', attachment['id'])
            except Exception as e:
                self.middleware.logger.warning('Unable to %s %r: %s', action, attachment['id'], e)

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)

    async def validate_set(self, state, verrors):
        if not state.snapshot_devices or not state.changed('snapdev') or state.effective('snapdev') != 'hidden':
            return

        namespaces = await self.middleware.call(
            'nvmet.namespace.query', [['device_type', '=', 'ZVOL']], {'select': ['device_path']}
        )
        if any(
            zvol_path_to_name(os.path.join('/dev', ns['device_path'])) in state.snapshot_devices for ns in namespaces
        ):
            verrors.add(
                state.attribute('snapdev'),
                f'{state.path!r} has snapshots which have attachments being used. Before marking it '
                'as HIDDEN, remove attachment usages.',
            )

    async def after_set(self, state):
        if state.type != 'VOLUME':
            return
        if state.changed('volsize'):
            await self.middleware.call('nvmet.namespace.resync_lun_size_for_zvol', state.path)


async def setup(middleware):
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate, NVMetNamespaceAttachmentDelegate(middleware)
    )
