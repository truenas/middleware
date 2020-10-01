from middlewared.service import private, Service


class UpdateService(Service):
    @private
    async def download_impl(self, job, train, location, progress_proportion):
        return await self.middleware.call('update.download_impl_scale', job, train, location, progress_proportion)
