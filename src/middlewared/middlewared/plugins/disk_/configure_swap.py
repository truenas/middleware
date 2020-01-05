import os
import platform
import subprocess

from collections import defaultdict

from middlewared.service import private, Service
from middlewared.utils import Popen, run

IS_LINUX = platform.system().lower() == 'linux'
MIRROR_MAX = 5


class DiskService(Service):

    @private
    async def swaps_configure(self):
        """
        Configures swap partitions in the system.
        We try to mirror all available swap partitions to avoid a system
        crash in case one of them dies.
        """
        used_partitions_in_mirror = set()
        create_swap_devices = []
        disks = [i async for i in await self.middleware.call('pool.get_disks')]
        disks.extend(await self.middleware.call('boot.get_disks'))
        existing_swap_devices = {'mirrors': [], 'partitions': []}
        for device in await self.middleware.call('disk.get_swap_devices'):
            if device.startswith('/dev/md') if IS_LINUX else device.startswith('mirror/'):
                # This is going to be complete path for linux and mirror/swapname.eli for freebsd
                existing_swap_devices['mirrors'].append(device)
            else:
                existing_swap_devices['partitions'].append(device)

        swap_mirrors = await self.middleware.call('disk.get_swap_mirrors')
        # disk.get_swap_mirrors is going to get us complete path for linux and mirror/swapname for freebsd
        # point to note is that we don't get .eli suffix from above - so we have to be careful here and use path
        # instead
        for mirror in swap_mirrors:
            # If the mirror is degraded or disk is not in a pool lets remove it
            if len(mirror['providers']) == 1 or any(
                p['disk'] not in disks for p in mirror['providers']
            ):
                await self.middleware.call('disk.swaps_remove_disks', [p['disk'] for p in mirror['providers']])
                if mirror['name'] in existing_swap_devices['mirrors']:
                    existing_swap_devices['mirrors'].remove(mirror['name'])
            else:
                mirror_name = mirror['path'] if IS_LINUX else mirror['path'].split('/dev/', 1)[-1]
                if mirror_name not in existing_swap_devices['mirrors']:
                    create_swap_devices.append(mirror_name)
                used_partitions_in_mirror.update(p['name'] for p in mirror['providers'])

                # If mirror has been configured automatically (not by middlewared)
                # and there is no geli attached yet we should look for core in it.
                if not IS_LINUX and mirror['config_type'] == 'AUTOMATIC' and not os.path.exists(mirror['path']):
                    await run(
                        'savecore', '-z', '-m', '5', '/data/crash/', f'/dev/{mirror_name}',
                        check=False
                    )

        if (len(existing_swap_devices['mirrors']) + len(existing_swap_devices['partitions'])) > MIRROR_MAX:
            return

        # Get all partitions of swap type, indexed by size
        swap_partitions_by_size = defaultdict(list)
        valid_swap_part_uuids = await self.middleware.call('disk.get_valid_swap_partition_type_uuids')
        all_partitions = {p['name']: p for p in await self.middleware.call('disk.list_all_partitions')}
        for swap_part in filter(
            lambda d: d['partition_type'] in valid_swap_part_uuids and d['name'] not in used_partitions_in_mirror,
            all_partitions.values()
        ):
            if not IS_LINUX:
                # Try to save a core dump from that.
                # Only try savecore if the partition is not already in use
                # to avoid errors in the console (#27516)
                await run('savecore', '-z', '-m', '5', '/data/crash/', f'/dev/{swap_part["name"]}', check=False)

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
                    for i in part_ab:
                        remove = False
                        if IS_LINUX:
                            part = all_partitions[i]['path']
                            if part in existing_swap_devices['partitions']:
                                remove = True
                        else:
                            part = i
                            if part in existing_swap_devices['partitions']:
                                remove = True
                            elif f'{part}.eli' in existing_swap_devices['partitions']:
                                part = f'{part}.eli'
                                remove = True

                        if remove:
                            await self.middleware.call('disk.swaps_remove_disks', [all_partitions[i]['disk']])
                            existing_swap_devices['partitions'].remove(part)
                except Exception:
                    self.logger.warn('Failed to remove disk from swap', exc_info=True)
                    # If something failed here there is no point in trying to create the mirror
                    continue

                part_a, part_b = part_ab

                if not IS_LINUX and not dumpdev:
                    dumpdev = await self.middleware.call('disk.dumpdev_configure', part_a)
                name = await self.middleware.call('disk.new_swap_name')
                if not name:
                    # Which means maximum has been reached and we can stop
                    break
                part_a_path, part_b_path = all_partitions[part_a]['path'], all_partitions[part_b]['path']
                if IS_LINUX:
                    cp = await Popen(
                        f'echo "y" | mdadm --create {os.path.join("/dev/md", name)} '
                        f'--level=1 --raid-devices=2 {part_a_path} {part_b_path}',
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
                    )
                else:
                    cp = await Popen(
                        ['gmirror', 'create', name, part_a_path, part_b_path],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    )
                stdout, stderr = await cp.communicate()
                if stderr:
                    self.logger.warning('Failed to create swap mirror %s: %s', name, stderr.decode())
                if cp.returncode:
                    continue

                create_swap_devices.append(os.path.join('/dev/md', name) if IS_LINUX else f'mirror/{name}')

            # Add remaining partitions to unused list
            unused_partitions += partitions

        if all(not existing_swap_devices[k] for k in existing_swap_devices) and unused_partitions:
            if not IS_LINUX and not dumpdev:
                await self.middleware.call('disk.dumpdev_configure', unused_partitions[0])
            create_swap_devices.append(
                all_partitions[unused_partitions[0]]['path'] if IS_LINUX else unused_partitions[0]
            )

        created_swap_devices = []
        for name in create_swap_devices:
            if IS_LINUX:
                try:
                    await run('mkswap', name)
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f'Failed to make swap for %s: %s', name, e.stderr.decode())
                    continue
            elif not IS_LINUX and not os.path.exists(os.path.join('/dev', f'{name}.eli')):
                try:
                    await run('geli', 'onetime', name)
                except subprocess.CalledProcessError as e:
                    self.logger.warning('Failed to encrypt swap partition %s: %s', name, e.stderr.decode())
                    continue

            try:
                await run('swapon', name if IS_LINUX else f'/dev/{name}.eli')
            except subprocess.CalledProcessError as e:
                self.logger.warning('Failed to activate swap partition %s: %s', name, e.stderr.decode())
                continue
            else:
                created_swap_devices.append(name)

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
            if not os.path.exists(os.path.join('/dev', 'md' if IS_LINUX else 'mirror', name)):
                return name
