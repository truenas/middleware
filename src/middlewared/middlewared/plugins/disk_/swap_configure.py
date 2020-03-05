import os
import subprocess

from collections import defaultdict

from middlewared.service import CallError, job, private, Service
from middlewared.utils import osc, run


MIRROR_MAX = 5


class DiskService(Service):

    @private
    @job(lock='swaps_configure')
    async def swaps_configure(self, job):
        """
        Configures swap partitions in the system.
        We try to mirror all available swap partitions to avoid a system
        crash in case one of them dies.
        """
        used_partitions_in_mirror = set()
        create_swap_devices = {}
        disks = [i async for i in await self.middleware.call('pool.get_disks')]
        disks.extend(await self.middleware.call('boot.get_disks'))
        existing_swap_devices = {'mirrors': [], 'partitions': []}
        mirrors = await self.middleware.call('disk.get_swap_mirrors')
        encrypted_mirrors = {m['encrypted_provider']: m for m in mirrors if m['encrypted_provider']}
        all_partitions = {p['name']: p for p in await self.middleware.call('disk.list_all_partitions')}

        for device in await self.middleware.call('disk.get_swap_devices'):
            if device in encrypted_mirrors or device.startswith(('/dev/md', '/dev/mirror/')):
                # This is going to be complete path for linux and freebsd
                existing_swap_devices['mirrors'].append(device)
            else:
                existing_swap_devices['partitions'].append(device)

        for mirror in mirrors:
            mirror_name = (mirror['encrypted_provider'] or mirror['real_path'])

            # If the mirror is degraded or disk is not in a pool lets remove it
            if mirror_name in existing_swap_devices['mirrors'] and (len(mirror['providers']) == 1 or any(
                p['disk'] not in disks for p in mirror['providers']
            )):
                await self.middleware.call('disk.swaps_remove_disks', [p['disk'] for p in mirror['providers']])
                existing_swap_devices['mirrors'].remove(mirror_name)
            else:
                if mirror_name not in existing_swap_devices['mirrors']:
                    create_swap_devices[mirror_name] = {
                        'path': mirror_name,
                        'encrypted_provider': mirror['encrypted_provider'],
                    }
                used_partitions_in_mirror.update(p['name'] for p in mirror['providers'])

                # If mirror has been configured automatically (not by middlewared)
                # and there is no geli attached yet we should look for core in it.
                if osc.IS_FREEBSD and mirror['config_type'] == 'AUTOMATIC' and not mirror['encrypted_provider']:
                    await run(
                        'savecore', '-z', '-m', '5', '/data/crash/', mirror_name,
                        check=False
                    )

        # Get all partitions of swap type, indexed by size
        swap_partitions_by_size = defaultdict(list)
        valid_swap_part_uuids = await self.middleware.call('disk.get_valid_swap_partition_type_uuids')
        for swap_part in filter(
            lambda d: d['partition_type'] in valid_swap_part_uuids and d['name'] not in used_partitions_in_mirror,
            all_partitions.values()
        ):
            if osc.IS_FREEBSD and not any(
                swap_part[k] in existing_swap_devices for k in ('encrypted_provider', 'path')
            ):
                # Try to save a core dump from that.
                # Only try savecore if the partition is not already in use
                # to avoid errors in the console (#27516)
                cp = await run('savecore', '-z', '-m', '5', '/data/crash/', f'/dev/{swap_part["name"]}', check=False)
                if cp.returncode:
                    self.middleware.logger.error(
                        'Failed to savecore for "%s": ', f'/dev/{swap_part["name"]}', cp.stderr.decode()
                    )

            if swap_part['disk'] in disks:
                swap_partitions_by_size[swap_part['size']].append(swap_part['name'])

        dumpdev = False
        unused_partitions = []
        for size, partitions in swap_partitions_by_size.items():
            # If we have only one partition add it to unused_partitions list
            if len(partitions) == 1:
                unused_partitions += partitions
                continue

            for i in range(int(len(partitions) / 2)):
                if (
                    len(create_swap_devices) + len(existing_swap_devices['mirrors']) +
                        len(existing_swap_devices['partitions'])
                ) > MIRROR_MAX:
                    break
                part_ab = partitions[0:2]
                partitions = partitions[2:]

                # We could have a single disk being used as swap, without mirror.
                try:
                    for p in part_ab:
                        remove = False
                        part_data = all_partitions[p]
                        if part_data['encrypted_provider'] in existing_swap_devices['partitions']:
                            part = part_data['encrypted_provider']
                            remove = True
                        elif part_data['path'] in existing_swap_devices['partitions']:
                            remove = True
                            part = part_data['path']

                        if remove:
                            await self.middleware.call('disk.swaps_remove_disks', [part_data['disk']])
                            existing_swap_devices['partitions'].remove(part)
                except Exception:
                    self.logger.warn('Failed to remove disk from swap', exc_info=True)
                    # If something failed here there is no point in trying to create the mirror
                    continue

                part_a, part_b = part_ab

                if osc.IS_FREEBSD and not dumpdev:
                    dumpdev = await self.middleware.call('disk.dumpdev_configure', part_a)
                swap_path = await self.middleware.call('disk.new_swap_name')
                if not swap_path:
                    # Which means maximum has been reached and we can stop
                    break
                part_a_path, part_b_path = all_partitions[part_a]['path'], all_partitions[part_b]['path']
                try:
                    await self.middleware.call(
                        'disk.create_swap_mirror', swap_path, {
                            'paths': [part_a_path, part_b_path],
                            'extra': {'level': 1} if osc.IS_LINUX else {},
                        }
                    )
                except CallError:
                    self.logger.warning('Failed to create swap mirror %s', swap_path)
                    continue

                swap_device = os.path.realpath(os.path.join(f'/dev/{"md" if osc.IS_LINUX else "mirror"}', swap_path))
                create_swap_devices[swap_device] = {
                    'path': swap_device,
                    'encrypted_provider': None,
                }

            # Add remaining partitions to unused list
            unused_partitions += partitions

        if unused_partitions and not create_swap_devices and all(
            not existing_swap_devices[k] for k in existing_swap_devices
        ):
            if osc.IS_FREEBSD and not dumpdev:
                await self.middleware.call('disk.dumpdev_configure', unused_partitions[0])
            swap_device = all_partitions[unused_partitions[0]]
            create_swap_devices[swap_device['path']] = {
                'path': swap_device['path'],
                'encrypted_provider': swap_device['encrypted_provider'],
            }

        created_swap_devices = []
        for swap_path, data in create_swap_devices.items():
            if osc.IS_LINUX:
                if not data['encrypted_provider']:
                    cp = await run(
                        'cryptsetup', '-d', '/dev/urandom', 'open', '--type', 'plain',
                        swap_path, swap_path.split('/')[-1], check=False, encoding='utf8',
                    )
                    if cp.returncode:
                        self.logger.warning('Failed to encrypt %s device: %s', swap_path, cp.stderr)
                        continue
                    swap_path = os.path.join('/dev/mapper', swap_path.split('/')[-1])
                else:
                    swap_path = data['encrypted_provider']
                try:
                    await run('mkswap', swap_path)
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f'Failed to make swap for %s: %s', swap_path, e.stderr.decode())
                    continue
            elif osc.IS_FREEBSD and not data['encrypted_provider']:
                try:
                    await run('geli', 'onetime', swap_path)
                except subprocess.CalledProcessError as e:
                    self.logger.warning('Failed to encrypt swap partition %s: %s', swap_path, e.stderr.decode())
                    continue
                else:
                    swap_path = f'{swap_path}.eli'

            try:
                await run('swapon', swap_path)
            except subprocess.CalledProcessError as e:
                self.logger.warning('Failed to activate swap partition %s: %s', swap_path, e.stderr.decode())
                continue
            else:
                created_swap_devices.append(swap_path)

        if existing_swap_devices['partitions'] and (created_swap_devices or existing_swap_devices['mirrors']):
            # This will happen in a case where a single partition existed initially
            # then other disks were added of different size. Now we don't use a single partition
            # for swap unless there is no existing partition/mirror already configured for swap.
            # In this case, we did create a mirror now and existing partitions should be removed from swap
            # as a mirror has been configured
            all_partitions_by_path = {
                p['encrypted_provider'] or p['path']: p['disk'] for p in all_partitions.values()
            }
            try:
                await self.middleware.call(
                    'disk.swaps_remove_disks', [
                        all_partitions_by_path[p] for p in existing_swap_devices['partitions']
                        if p in all_partitions_by_path
                    ]
                )
            except Exception as e:
                self.logger.warning(
                    'Failed to remove %s from swap: %s', ','.join(existing_swap_devices['partitions']), str(e)
                )
            else:
                existing_swap_devices['partitions'] = []

        return existing_swap_devices['partitions'] + existing_swap_devices['mirrors'] + created_swap_devices

    @private
    def new_swap_name(self):
        """
        Get a new name for a swap mirror

        Returns:
            str: name of the swap mirror
        """
        for i in range(MIRROR_MAX):
            name = f'swap{i}'
            if not os.path.exists(os.path.join('/dev', 'md' if osc.IS_LINUX else 'mirror', name)):
                return name
