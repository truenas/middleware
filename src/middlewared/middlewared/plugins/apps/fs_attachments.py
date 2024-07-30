from middlewared.common.attachment import FSAttachmentDelegate


class AppFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'apps'
    title = 'Apps'

    async def query(self, path, enabled, options=None):
        apps_attached = []
        for app in await self.middleware.call('app.query'):
            if not app['active_workloads']['volumes'] or (
                app['state'] == 'STOPPED' if enabled else app['state'] != 'STOPPED'
            ):
                continue

            if await self.middleware.call(
                'filesystem.is_child', [volume['source'] for volume in app['active_workloads']['volumes']], path
            ):
                apps_attached.append({
                    'id': app['name'],
                    'name': app['name'],
                })

        return apps_attached

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                await (await self.middleware.call('app.stop', attachment['id'])).wait(raise_error=True)
            except Exception:
                self.middleware.logger.error('Unable to stop %r app', attachment['id'], exc_info=True)

    async def toggle(self, attachments, enabled):
        # if enabled is true - we are going to ignore that as we don't want to scale up releases
        # automatically when a path becomes available
        for attachment in ([] if enabled else attachments):
            action = 'start' if enabled else 'stop'
            try:
                await (await self.middleware.call(f'app.{action}', attachment['id'])).wait(raise_error=True)
            except Exception:
                self.middleware.logger.error('Unable to %s %r app', action, attachment['id'], exc_info=True)

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    middleware.create_task(
        middleware.call('pool.dataset.register_attachment_delegate', AppFSAttachmentDelegate(middleware))
    )
