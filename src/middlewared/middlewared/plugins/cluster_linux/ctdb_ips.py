import errno
import json
import os
import pathlib

from middlewared.service import Service, CallError
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.pyglfs_utils import glusterfs_volume, lock_file_open


class CtdbIpService(Service):

    class Config:
        namespace = 'ctdb.ips'
        private = True

    async def common_validation(self, data, schema_name, verrors):

        # make sure that the cluster shared volume is mounted
        if not await self.middleware.call('service.started', 'glusterd'):
            verrors.add(
                f'{schema_name}.glusterd',
                'The "glusterd" service is not started.',
            )

        shared_vol = pathlib.Path(data['volume_mountpoint'])

        try:
            mounted = shared_vol.is_mount()
        except Exception:
            mounted = False

        if not mounted:
            verrors.add(
                f'{schema_name}.{shared_vol}',
                f'"{shared_vol}" is not mounted'
            )

        verrors.check()

        if schema_name in ('private_create', 'public_create'):
            existing_public_ips = {}

            if schema_name == 'public_create':
                public_ips_for_node = await self.middleware.call(
                    'ctdb.public.ips.query', [('pnn', '=', data['pnn'])]
                )
                if public_ips_for_node:
                    existing_public_ips = public_ips_for_node[0]['configured_ips']

            if data['ip'] in existing_public_ips:
                verrors.add(
                    f'{schema_name}.{data["ip"]}',
                    f'"{data["ip"]}" is already added as a public IP address.'
                )
            elif data['ip'] in [i['address'] for i in (await self.middleware.call('ctdb.private.ips.query'))]:
                verrors.add(
                    f'{schema_name}.{data["ip"]}',
                    f'"{data["ip"]}" is already added as a private IP address.'
                )
            elif schema_name == 'public_create':
                if data['interface'] not in [i['id'] for i in await self.middleware.call('interface.query')]:
                    verrors.add(
                        f'{schema_name}.{data["interface"]}',
                        f'"{data["interface"]}" not found on this system.',
                    )

        elif schema_name == 'public_delete':
            return

        else:
            address = data.get('address') or data['public_ip']

            # data['enable'] is the update request
            # data['enabled'] is the current status in cluster
            if not data['enable'] and not data['enabled']:
                verrors.add(
                    f'{schema_name}.{address}',
                    f'"{address}" is already disabled in the cluster.'
                )
            elif data['enable'] and data['enabled']:
                verrors.add(
                    f'{schema_name}.{address}',
                    f'"{address}" is already enabled in the cluster.'
                )

        verrors.check()

    @glusterfs_volume
    def contents(self, vol, data):
        parent = vol.open_by_uuid(data['uuid'])
        try:
            obj = parent.lookup(data['ip_file'])
        except Exception:
            # TODO: we probably need to raise an exception here for better handling
            self.logger.warning('%s: lookup failed.', data['path'], exc_info=True)
            return []

        try:
            with lock_file_open(obj, os.O_RDONLY):
                return obj.contents().decode().splitlines()
        except Exception:
            self.logger.warning('%s: failed to read file contents', data['path'], exc_info=True)

        return []

    def entry_check(self, ip_file, entry, file_size):
        # Scan file for duplicate entry. Ideally this sort
        # of issue would have been caught during initial validation
        # but since initial validation isn't performed under a lock,
        # we are potentially exposed to time of user / time of check issues.
        contents = ip_file.pread(0, file_size)
        for line in contents.decode().splitlines():
            if line == entry:
                raise CallError(f'{entry}: entry already exists in file.', errno.EEXIST)

    def create_locked(self, ctdb_file, data, is_private):
        # in the case of adding a node (private or public),
        # it _MUST_ be added to the end of the file always
        with lock_file_open(ctdb_file, os.O_RDWR, mode=0o644, owners=(0, 0)) as f:
            st = f.fstat()
            entry = data['ip'] if is_private else f'{data["ip"]}/{data["netmask"]} {data["interface"]}'
            if is_private:
                gluster_info = {'uuid': data['node_uuid']}
                entry += f'#{json.dumps(gluster_info)}'
            if st.st_size > 0:
                self.entry_check(f, entry, st.st_size)
            f.pwrite((entry + '\n').encode(), st.st_size)

    def update_locked(self, schema_name, ctdb_file, data, is_private):
        enable = data.get('enable', False)

        with lock_file_open(ctdb_file, os.O_RDWR, mode=0o644, owners=(0, 0)) as f:
            st = f.fstat()
            lines = []
            if is_private:
                address = data['address']
            else:
                address = data["public_ip"]

            find_entry = address if not enable else '#' + address

            # read the data first
            if st.st_size > 0:
                lines.extend(f.pread(0, st.st_size).decode().splitlines())

            # before we truncate the file, let's make sure we don't hit an
            # unexpected error
            try:
                if is_private:
                    index = None

                    for idx, entry in enumerate(lines):
                        if entry.startswith(f'{find_entry}#'):
                            index = idx
                            break

                    if index is None:
                        raise IndexError(f'{find_entry}: not found')

                    # on private ip file update, `new_entry` is just the inverse
                    # of `find_entry`.
                    # (i.e if find_entry = '192.168.1.150' new_entry = '#192.168.1.150')
                    new_entry = address if find_entry.startswith('#') else '#' + address
                    gluster_info = {'uuid': data['node_uuid']}
                    new_entry += f'#{json.dumps(gluster_info)}'
                else:
                    # on public ip update, ctdb doesn't return the netmask information
                    # for the associated ip even though it requires one when creating.
                    # this means get the index, and simply add a '#' or remove it from
                    # that entry depending on what the update operation is
                    index = lines.index(next(i for i in lines if i.startswith(find_entry)))
                    old_entry = lines[index]
                    new_entry = '#' + old_entry if not old_entry.startswith('#') else old_entry.split('#')[1]

                # replace our old entry with the new one
                # if we're deleting a public IP address, remove the entry completely.
                if schema_name != 'public_delete':
                    lines[index] = new_entry
                else:
                    lines.pop(index)
            except ValueError as e:
                raise CallError(f'Failed finding entry in file with error: {e}')

            contents = '\n'.join(lines) + '\n'

            # now truncate the file since we're rewriting it
            f.ftruncate(0)
            f.pwrite(contents.encode(), 0)

    @glusterfs_volume
    def update_file(self, vol, data, schema_name):
        """
        Update the ctdb cluster private or public IP file.
        """

        is_private = schema_name in ('private_create', 'private_update')
        create = schema_name in ('private_create', 'public_create')
        root_hdl = vol.open_by_uuid(data['uuid'])
        file_hdl = None

        if is_private:
            glfs_file = CTDBConfig.PRIVATE_IP_FILE.value
            etc_file = pathlib.Path(CTDBConfig.ETC_PRI_IP_FILE.value)
        else:
            glfs_file = f'{CTDBConfig.PUBLIC_IP_FILE.value}_{data["pnn"]}'
            etc_file = pathlib.Path(CTDBConfig.ETC_PUB_IP_FILE.value)

        ctdb_file = pathlib.Path(data['mountpoint'], glfs_file)

        if is_private:
            # ctdb documentation is _VERY_ explicit in
            # how the private IP file is modified

            # the documentation clearly states that before
            # adding a private peer, the cluster must be
            # healthy. This requires running a command that
            # is expecting the ctdb daemon to be started.
            # If this is the first private peer being added
            # then the ctdb daemon isn't going to be started
            # which means we can't check if the cluster is
            # healthy. So we do the following:
            #   1. if the ctdb shared volume private ip file exists
            #       then assume that this isn't the first peer
            #       being added to the cluster and check the ctdb
            #       daemon for the cluster health.
            #   2. elif the ctdb shared volume private ip doesnt
            #       exist then assume this is the first peer being
            #       added to the cluster and skip the cluster health
            #       check.
            try:
                file_hdl = root_hdl.lookup(glfs_file)
            except Exception:
                pass
            else:
                if self.middleware.call_sync('service.started', 'ctdb'):
                    if not self.middleware.call_sync('ctdb.general.healthy'):
                        raise CallError('ctdb cluster is not healthy, not updating private ip file')

        # create the ctdb shared volume file
        # ignoring if it's already there
        if not file_hdl:
            try:
                file_hdl = root_hdl.create(glfs_file, flags=os.O_RDWR | os.O_CREAT)
            except Exception as e:
                raise CallError(f'Failed creating {ctdb_file} with error: {e}')

        # we need to make sure the local etc file is symlinked
        # to the ctdb shared volume so all nodes in the cluster
        # have the same config
        symlink_it = delete_it = False
        if etc_file.exists():
            if not etc_file.is_symlink():
                # delete it since we're symlinking it
                delete_it = True
            elif etc_file.resolve() != ctdb_file:
                # means it's a symlink but not to the ctdb
                # shared volume ip file
                delete_it = True
        else:
            symlink_it = True

        # delete the file
        if delete_it:
            try:
                etc_file.unlink()
            except Exception as e:
                raise CallError(f'Failed deleting {etc_file} with error: {e}')

        # symlink the file
        if symlink_it:
            try:
                etc_file.symlink_to(ctdb_file)
            except Exception as e:
                raise CallError(f'Failed symlinking {etc_file} to {ctdb_file} with error: {e}')

        if create:
            self.create_locked(file_hdl, data, is_private)
        else:
            self.update_locked(schema_name, file_hdl, data, is_private)

        if not is_private:
            self.middleware.call_sync('ctdb.public.ips.reload')
