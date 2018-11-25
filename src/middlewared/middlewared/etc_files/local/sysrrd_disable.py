import os
import tarfile


SYSRRD_SENTINEL = '/data/sentinels/sysdataset-rrd-disable'


def rename_tarinfo(tarinfo):
    name = tarinfo.name.split('/', maxsplit=4)
    tarinfo.name = f'collectd/rrd/{"" if len(name) < 5 else name[-1]}'
    return tarinfo


def sysrrd_disable(middleware):
    # skip if no sentinel is found
    if os.path.exists(SYSRRD_SENTINEL):
        systemdataset_config = middleware.call_sync('systemdataset.config')
        rrd_mount = f'{systemdataset_config["path"]}/rrd-{systemdataset_config["uuid"]}'
        if os.path.isdir(rrd_mount):
            # Let's create tar from system dataset rrd which collectd.conf understands
            with tarfile.open('/data/rrd_dir.tar.bz2', mode='w:bz2') as archive:
                archive.add(rrd_mount, filter=rename_tarinfo)

        os.remove(SYSRRD_SENTINEL)


async def render(service, middleware):
    await middleware.run_in_thread(sysrrd_disable, middleware)
