from middlewared.service import CallError, Service
from middlewared.utils import run

from .boot_disk_base import BootDiskBase


class BootService(Service, BootDiskBase):

    async def format(self, dev, options):
        job = await self.middleware.call('disk.wipe', dev, 'QUICK')
        await job.wait()
        if job.error:
            raise CallError(job.error)

        commands = []
        boot_type = await self.middleware.call('boot.get_boot_type')
        if boot_type == 'EFI':
            commands.append(
                ('sgdisk', '-a=4096', '-n1:24K:+512M', '-t1:EF00', f'/dev/{dev}')
            )
        else:
            commands.append(
                ('sgdisk', '-a=4096', '-n1:24K:+1000K', '-t1:EF02', f'/dev/{dev}')
            )
        part_num = 2
        if options.get('swap_size'):
            commands.append(
                ('sgdisk', '-a=4096', f'-n2:0:{options["swap_size"]}', '-t2:8200', f'/dev/{dev}'),
            )
            part_num = 3

        commands.append(
            ('sgdisk', f'-n{part_num}:0:{options.get("size") or "0"}', f'-t{part_num}:BF01', f'/dev/{dev}')
        )

        # TODO: Let's catch no space left here and handle it accordingly
        for command in commands:
            p = await run(*command, check=False)
            if p.returncode != 0:
                raise CallError(
                    '%r failed:\n%s%s' % (' '.join(command), p.stdout.decode('utf-8'), p.stderr.decode('utf-8'))
                )

        return boot_type
