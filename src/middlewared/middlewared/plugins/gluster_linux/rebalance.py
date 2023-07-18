import errno

from glustercli.cli import rebalance

from middlewared.service import Service, CallError, accepts, job
from middlewared.schema import Dict, Str, Bool
from middlewared.utils import filter_list
from middlewared.validators import UUID
from time import sleep

LOCK = 'rebalance_lock'


class GlusterRebalanceService(Service):

    class Config:
        namespace = 'gluster.rebalance'
        cli_namespace = 'service.gluster.rebalance'
        private = True

    async def stop_or_status_impl(self, gvol, op):
        method = rebalance.stop if op == 'stop' else rebalance.status
        rv = {}
        try:
            rv = await self.middleware.call('gluster.method.run', method, {'args': (gvol,)})
        except CallError as e:
            if 'Rebalance not started for volume' in str(e):
                # dont treat this as an error
                return rv
            else:
                raise
        else:
            return rv

    @accepts(Dict(
        'rebalance_task_wait',
        Str('volume_name', required=True),
        Str('task_id', validators=[UUID()], required=True)
    ))
    @job(lock=lambda args: f'rebalance_task_wait_{args}')
    async def rebalance_task_wait(self, job, data):
        """
        This method can potentially be extremely long-running and so we only poll every
        30 seconds.

        Returns `gluster.rebalance.status` on successful completion
        """
        def get_failed(st):
            return filter_list(st['nodes'], [['status', '=', 'failed']])

        def get_remaining(st):
            return filter_list(st['nodes'], [['status', 'nin', ['completed', 'failed', 'stopped']]])

        def check_status(st):
            if st['task_id'] != data['task_id']:
                raise CallError(f'{data["task_id"]}: rebalance task not found for volume %s', errno.ENOENT)

            if (failed := get_failed(st)):
                names = ', '.join(x['node_name'] for x in failed)
                raise CallError(f'The following nodes have failed status: {names}')

            return get_remaining(st)

        initial_status = await self.status({'name': data['volume_name']})
        if not (remaining := check_status(initial_status)):
            # Everything is complete
            return initial_status

        while remaining:
            sleep(10)
            remaining = check_status(await self.status({'name': data['volume_name']}))
            percent_nodes_remaining = len(remaining) / len(initial_status['nodes'])
            remaining_names = [x['node_name'] for x in remaining]
            if remaining_names:
                job.set_progress(
                    100 - int(percent_nodes_remaining),
                    f'Waiting for following nodes to complete rebalance: {", ".join(remaining_names)}'
                )

        return await self.status({'name': data['volume_name']})

    @accepts(Dict('fix_layout', Str('name', required=True)))
    @job(lock=LOCK)
    async def fix_layout(self, job, data):
        """
        Fix the directory layout on gluster volume named `name`. This is a private endpoint
        and is expected to only be called via a public facing endpoint since this doesn't do
        any validation. The callers are expected to validate the data before calling this.

        Fixing the layout is necessary because the layout structure is static for a given directory.
        Even after new bricks are added to the volume, newly created files in existing directories will
        still be distributed only among the original bricks. Running this endpoint will fix the layout
        information so that the files can be created on the newly added bricks.

        `name` str: name of existing gluster volume.
        """
        job.set_progress(50, f'Starting fix-layout operation on {data["name"]!r}')
        options = {'args': (data['name'],)}
        await self.middleware.call('gluster.method.run', rebalance.fix_layout_start, options)
        job.set_progress(100, f'Successfully started fix-layout operation on {data["name"]!r}')
        return await self.stop_or_status_impl(data['name'], 'status')

    @accepts(Dict('rebalance_start', Str('name', required=True), Bool('force', default=False)))
    @job(lock=LOCK)
    async def start(self, job, data):
        """
        Fix the directory layout and migrate existing data to the newly added brick(s). This behaves the
        exact same way as the `gluster.rebalance.fix_layout` endpoint, but this one will also migrate the
        existing data (rebalance) to the newly added brick(s).

        `name` str: name of existing gluster volume.
        `force` bool: If True, will forcefully start rebelance operation on `name`.
        """
        job.set_progress(50, f'Starting rebalance operation on {data["name"]!r}')
        vol_name = data.pop('name')
        options = {'args': (vol_name,), 'kwargs': data}
        await self.middleware.call('gluster.method.run', rebalance.start, options)
        job.set_progress(100, f'Successfully started rebalance operation on {vol_name!r}')
        return await self.stop_or_status_impl(vol_name, 'status')

    @accepts(Dict('rebalance_stop', Str('name', required=True)))
    @job(lock=LOCK)
    async def stop(self, job, data):
        """
        Stop a rebalance operation on gluster volume with name `name`.
        """
        return await self.stop_or_status_impl(data['name'], 'stop')

    @accepts(Dict('rebalance_status', Str('name', required=True)))
    async def status(self, data):
        """
        Return rebalance status information for gluster volume with name `name`.
        """
        return await self.stop_or_status_impl(data['name'], 'status')
