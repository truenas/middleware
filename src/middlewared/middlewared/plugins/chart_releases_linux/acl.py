from middlewared.service import CallError, private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def apply_acls(self, acls_to_apply):
        bulk_job = await self.middleware.call(
            'core.bulk', 'filesystem.add_to_acl', [[acls_to_apply[acl_path]] for acl_path in acls_to_apply],
        )
        await bulk_job.wait()

        failures = []
        for status, acl_path in zip(bulk_job.result, acls_to_apply):
            if status['error']:
                failures.append(acl_path)

        if failures:
            raise CallError(f'Failed to apply ACLs to the following paths: {", ".join(failures)!r}')
