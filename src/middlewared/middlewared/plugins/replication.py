from middlewared.schema import accepts, Dict, Str, Int, Bool, Ref
from middlewared.service import private, CallError, Service, CRUDService, filterable, job, periodic
from middlewared.utils import Popen

import subprocess
import libzfs
import paramiko


compression_cmd = {
    'pigz': ('| /usr/local/bin/pigz ', ' /usr/bin/env pigz -d |'),
    'plzip': ('| /usr/local/bin/plzip ', ' /usr/bin/env plzip -d |'),
    'lz4': ('| /usr/local/bin/lz4c ', ' /usr/bin/env lz4c -d |'),
    'xz': ('| /usr/bin/xz ', ' /usr/bin/env xzdec |'),
}


def find_latest_common_snap(local, remote):
    last_remote_snap = remote[-1]
    if isinstance(last_remote_snap, libzfs.ZFSSnapshot):
        last_remote_snap_guid = last_remote_snap.properties['guid'].value
    else:
        last_remote_snap_guid = last_remote_snap['guid']

    for snap in local:
        if isinstance(snap, libzfs.ZFSSnapshot):
            if snap.properties['guid'].value == last_remote_snap_guid:
                return snap.name


def find_snaps_to_delete(local, remote):
    local_snaps = []
    snaps_to_remove = []
    for snap in local:
        if isinstance(snap, libzfs.ZFSSnapshot):
            local_snaps.append(snap.snapshot_name)
        else:
            local_snaps.append(snap['name'])

    for snap in remote:
        if isinstance(snap, libzfs.ZFSSnapshot):
            if snap.snapshot_name not in local_snaps:
                snaps_to_remove.append(snap.snapshot_name)
        else:
            if snap['name'] not in local_snaps:
                snaps_to_remove.append(snap['name'])

    return snaps_to_remove


class ReplicationTask(CRUDService):

    class Config:
        namespace = 'replication.task'

    @filterable
    async def query(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', 'storage.replication', filters, options)

    @accepts(Dict(
        'replication-task',
        Str('name'),
        Str('repl_filesystem'),
        Int('repl_snap_task'),
        Bool('recursive'),
        Int('repl_peer'),
        Str('repl_remote'),
        Str('repl_zfs'),
        Str('repl_userepl'),
        Bool('repl_followdelete'),
        Str('repl_compression'),
        Str('repl_limit'),
        Int('repl_end'),
        Bool('repl_enabled'),
        Bool('new_repl_engine'),
        Bool('repl_resume'),
        Bool('repl_ssh_mbuffer'),
        Str('repl_type'),
        Str('repl_transport'),
        Str('repl_last_begin'),
        Str('repl_last_end'),
        Str('repl_result'),
        Bool('repl_userepl'),
        register=True,
    ))
    async def do_create(self, data):
        return await self.middleware.call(
            'datastore.insert',
            'storage.replication',
            data,
        )

    @accepts(Int('id'), Ref('replication-task'))
    async def do_update(self, id, data):
        return await self.middleware.call(
            'datastore.update',
            'storage.replication',
            id,
            data,
        )

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            'storage.replication',
            id,
        )


    @job(process=True)
    async def start_local_replication(self, job, repl_task_id):
        zfs = libzfs.ZFS()

        try:
            repl_task = await self.middleware.call(
                'replication.task.query',
                [('id', '=', repl_task_id)],
                {'get': True}
            )
        except IndexError:
            raise CallError(f'Task {repl_task_id} does not exists')

        src_dataset_name = repl_task.get('repl_filesystem')
        dest_dataset_name = repl_task.get('repl_zfs')

        try:
            src_dataset = zfs.get_dataset(src_dataset_name)
        except libzfs.ZFSException as e:
            await self.do_update(repl_task_id, {'repl_result': e})
            raise CallError(e)
        else:
            src_snapshots = src_dataset.snapshots
            snap_sorted_s = sorted(src_snapshots, key=lambda x: x.properties['createtxg'].rawvalue)

        try:
            dest_dataset = zfs.get_dataset(dest_dataset_name)
            token = dest_dataset.properties.get('receive_resume_token')
        except libzfs.ZFSException:
            dest_pool = await self.middleware.call(
                'zfs.pool.query',
                [('name', '=', dest_dataset_name.split('/')[0])]
            )
            if dest_pool:
                sender = subprocess.Popen(
                        ['zfs', 'send', '-p', snap_sorted_s[-1].name],
                        stdout=subprocess.PIPE
                    )
            else:
                await self.do_update(repl_task_id, {'repl_result': 'Destination pool does not exists'})
                raise CallError('Destination pool does not exists')
        else:

            if token.value and repl_task['repl_resume']:
                sender = subprocess.Popen(
                    ['zfs', 'send', '-t', '-p', token.value, dest_dataset_name],
                    stdout=subprocess.PIPE
                )
            elif token.value and not repl_task['repl_resume']:
                subprocess.Popen(['zfs', 'recv', '-A', dest_dataset_name])

            else:
                dest_snapshots = src_dataset.snapshots
                snap_sorted_r = sorted(dest_snapshots, key=lambda x: x.properties['createtxg'].rawvalue)
                last_common_snapshot = find_latest_common_snap(snap_sorted_s, snap_sorted_r)

                if last_common_snapshot.split('/')[-1] == snap_sorted_s[-1].name:
                    await self.do_update(repl_task_id, {'repl_result': f'Destination dataset already has the newest snapshot'})
                    return False
                else:
                    sender = subprocess.Popen(
                        ['zfs', 'send', '-p', '-I', last_common_snapshot, snap_sorted_s[-1].name],
                        stdout=subprocess.PIPE)

        receiver = subprocess.Popen(
            ['zfs', 'recv', '-s' if repl_task['repl_resume'] else '', repl_task['repl_zfs']],
            stdin=sender.stdout
        )

        while True:
            # Just for PoC
            if sender.poll() is not None or receiver.poll() is not None:
                receiver.terminate()
                sender.terminate()
                await self.do_update(repl_task_id, {'repl_result': f'Sending process finished with {sender.returncode} retruncode and receiving with {receiver.returncode}'})
                break

        if repl_task['repl_followdelete']:
            snaps_to_delete = find_snaps_to_delete(snap_sorted_s, snap_sorted_r)
            for snap in snaps_to_delete:
                snap = zfs.get_snapshot(snap)
                snap.delete(True)

        return True

    @job(process=True)
    async def start_ssh_replication(self, job, repl_task_id):
        zfs = libzfs.ZFS()

        try:
            repl_task = await self.middleware.call(
                'replication.task.query',
                [('id', '=', repl_task_id)],
                {'get': True}
            )
        except IndexError:
            raise CallError(f'Task {repl_task_id} does not exists')

        try:
            peer = await self.middleware.call(
                'peer.ssh.query',
                [('peer_ptr', '=', repl_task['repl_peer']['id'])],
                {'get': True}
            )
        except IndexError:
            raise CallError(f'SSH Peer does not exist')

        src_dataset_name = repl_task.get('repl_filesystem')
        dest_dataset_name = repl_task.get('repl_zfs')

        if repl_task['repl_ssh_mbuffer']:
            mbuffer_r = '/usr/local/bin/mbuffer -s 128k -m 1G |'
            mbuffer_w = '| /usr/local/bin/mbuffer -s 128k -m 1G'
        else:
            mbuffer_r, mbuffer_w = '', ''

        if repl_task['repl_compression'] != 'off':
            comp_r = compression_cmd[repl_task['repl_compression']][1]
            comp_w = compression_cmd[repl_task['repl_compression']][0]
        else:
            comp_r, comp_w = '', ''

        try:
            src_dataset = zfs.get_dataset(src_dataset_name)
        except libzfs.ZFSException as e:
            await self.do_update(repl_task_id, {'repl_result': e})
            raise CallError(e)
        else:
            src_snapshots = src_dataset.snapshots
            snap_sorted_s = sorted(src_snapshots, key=lambda x: x.properties['createtxg'].rawvalue)

        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.connect(peer['ssh_remote_hostname'], port=peer['ssh_port'], username=peer['ssh_remote_user'])
        except paramiko.AuthenticationException as e:
            await self.do_update(repl_task_id, {'repl_result': e})
            raise CallError(e)

        stdin, stdout, stderr = client.exec_command(f'/sbin/zfs list {dest_dataset_name}')

        if stdout.channel.exit_status:
            stdin, stdout, stderr = client.exec_command(f"/sbin/zpool list {dest_dataset_name.split('/')[0]}")
            if stdout.channel.exit_status:
                err_message = stderr.readline()
                await self.do_update(repl_task_id, {'repl_result': err_message})
                raise CallError(err_message)
            else:
                sender = subprocess.Popen(
                    f"zfs send -p {snap_sorted_s[-1].name} {comp_w} {mbuffer_w}| ssh root@{peer['ssh_remote_hostname']} '{mbuffer_r} {comp_r} zfs recv {dest_dataset_name}'",
                    shell=True
                )
                output, error = sender.communicate()
                if sender.returncode:
                    await self.do_update(repl_task_id, {'repl_result': f'{error}'})
                    return False

        else:
            stdin, stdout, stderr = client.exec_command(
                f'/sbin/zfs get -H -p -o value receive_resume_token {dest_dataset_name}'
            )
            if not stdout.channel.exit_status:
                token = stdout.readlines()[0].strip('\n')
                if token != '-' and repl_task['repl_resume']:
                    subprocess.Popen(
                        f"zfs send -p -t {token} {comp_w} {mbuffer_w}| ssh root@{peer['ssh_remote_hostname']} '{mbuffer_r} {comp_r} zfs recv {dest_dataset_name}'",
                        shell=True
                    )
                elif token != '-' and not repl_task['repl_resume']:
                    subprocess.Popen(
                        f"ssh root@{peer['ssh_remote_hostname']} zfs recv -A {dest_dataset_name}",
                        shell=True
                    )
                else:
                    stdin, stdout, stderr = client.exec_command(
                        f'/sbin/zfs list -H -t snapshot -p -o name,guid,createtxg -r -d 1 {dest_dataset_name}'
                    )

                if stdout.channel.exit_status:
                    err_message = stderr.readline()
                    await self.do_update(repl_task_id, {'repl_result': err_message})
                    raise CallError(err_message)

                else:
                    dest_snapshots = []
                    dest_snapshots_list = stdout.readlines()
                    if dest_snapshots_list:
                        for snap in dest_snapshots_list:
                            parsed_snap = snap.replace('\n', '').split('\t')
                            dest_snapshots.append(
                                {'name': parsed_snap[0], 'guid': parsed_snap[1], 'txg': parsed_snap[2]}
                            )
                    snap_sorted_r = sorted(dest_snapshots, key=lambda x: x['txg'])
                    last_common_snapshot = find_latest_common_snap(snap_sorted_s, snap_sorted_r)

                    if last_common_snapshot.split('/')[-1] == snap_sorted_s[-1].name:
                        await self.do_update(repl_task_id, {'repl_result': f'Destination dataset already has the newest snapshot'})
                        return False

                    else:
                        sender = subprocess.Popen(
                            f"zfs send -p -I {last_common_snapshot} {snap_sorted_s[-1].name} | ssh root@{peer['ssh_remote_hostname']} '{mbuffer_r} zfs recv {dest_dataset_name}'",
                            shell=True
                        )
                        output, error = sender.communicate()
                        if sender.returncode:
                            await self.do_update(repl_task_id, {'repl_result': f'{error}'})
                            return False

                    if repl_task['repl_followdelete']:
                        snaps_to_delete = find_snaps_to_delete(snap_sorted_s, snap_sorted_r)
                        
                        stdin, stdout, stderr = client.exec_command(
                            f'/sbin/zfs destroy -d {dest_dataset_name}' + '@' + ','.join([snap.split('@')[-1] for snap in snaps_to_delete])
                        )

        await self.do_update(repl_task_id, {'repl_result': 'Success'})
        return True
