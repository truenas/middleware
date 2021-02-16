import pathlib

from middlewared.service import Service, CallError
from middlewared.plugins.cluster_linux.utils import CTDBConfig


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

        try:
            shared_vol = pathlib.Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
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
            if data['ip'] in [i['public_ip'] for i in (await self.middleware.call('ctdb.public.ips.query'))]:
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

    def update_file(self, data, schema_name):
        """
        Update the ctdb cluster private or public IP file.
        """

        is_private = schema_name in ('private_create', 'private_update')
        create = schema_name in ('private_create', 'public_create')
        enable = data.get('enable', False)

        if is_private:
            ctdb_file = pathlib.Path(CTDBConfig.GM_PRI_IP_FILE.value)
            etc_file = pathlib.Path(CTDBConfig.ETC_PRI_IP_FILE.value)
        else:
            ctdb_file = pathlib.Path(CTDBConfig.GM_PUB_IP_FILE.value)
            etc_file = pathlib.Path(CTDBConfig.ETC_PUB_IP_FILE.value)

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
            if ctdb_file.exists() and self.middleware.call_sync('service.started', 'ctdb'):
                if not self.middleware.call_sync('ctdb.general.healthy'):
                    raise CallError('ctdb cluster is not healthy, not updating private ip file')

        # create the ctdb shared volume file
        # ignoring if it's already there
        try:
            ctdb_file.touch(exist_ok=True)
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
            # in the case of adding a node (private or public),
            # it _MUST_ be added to the end of the file always
            with open(ctdb_file, 'a') as f:
                if is_private:
                    f.write(data['ip'] + '\n')
                else:
                    entry = f'{data["ip"]}/{data["netmask"]} {data["interface"]}'
                    f.write(entry + '\n')
        else:
            if is_private:
                address = data['address']
            else:
                address = data["public_ip"]

            find_entry = address if not enable else '#' + address

            # no matter what we're doing at this point,
            # we're going to have to read, truncate,
            # and rewrite the contents.
            with open(ctdb_file, 'r+') as f:
                # read the data first
                lines = f.read().splitlines()

                # before we truncate the file, let's make sure we don't hit an
                # unexpected error
                try:
                    if is_private:
                        index = lines.index(find_entry)
                        # on private ip file update, `new_entry` is just the inverse
                        # of `find_entry`.
                        # (i.e if find_entry = '192.168.1.150' new_entry = '#192.168.1.150')
                        new_entry = address if find_entry.startswith('#') else '#' + address
                    else:
                        # on public ip update, ctdb doesn't return the netmask information
                        # for the associated ip even though it requires one when creating.
                        # this means get the index, and simply add a '#' or remove it from
                        # that entry depending on what the update operation is
                        index = lines.index(next(i for i in lines if i.startswith(find_entry)))
                        old_entry = lines[index]
                        new_entry = '#' + old_entry if not old_entry.startswith('#') else old_entry.split('#')[1]

                    # replace our old entry with the new one
                    lines[index] = new_entry
                except ValueError as e:
                    raise CallError(f'Failed finding entry in file with error: {e}')

                # now truncate the file since we're rewriting it
                f.seek(0)
                f.truncate()

                # finally write it
                f.write('\n'.join(lines) + '\n')
