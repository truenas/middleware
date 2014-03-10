#!/usr/local/bin/python

import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models.loading import cache
cache.get_apps()

from freenasUI.common.system import get_system_dataset
from freenasUI.common.pipesubr import pipeopen
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.system.models import Advanced


def dataset_exists(dataset):
    res = False
    p = pipeopen("/sbin/zfs list -H '%s'" % dataset)
    p.communicate()
    if p.returncode == 0:
        res = True

    return res


def create_system_datasets_zfs(system_dataset, system_datasets):
    if not dataset_exists(system_dataset):
        rv, msg = notifier().create_zfs_dataset(system_dataset)
        if rv != 0:
            print >> sys.stderr, "Unable to create %s: %s" % (system_dataset, msg)
            sys.exit(1)
        os.chmod("/mnt/%s" % system_dataset, 0755)

    for ds in system_datasets:
        dataset = "%s/%s" % (system_dataset, ds)
        if dataset_exists(dataset):
            continue

        rv, msg = notifier().create_zfs_dataset(dataset)
        if rv != 0 or not dataset_exists(dataset):
            print >> sys.stderr, "Unable to create %s: %s" % (dataset, msg)
            sys.exit(1)
        os.chmod("/mnt/%s" % dataset, 0755)


def create_system_datasets_ufs(system_dataset, system_datasets):
    system_dataset = "/mnt/%s" % system_dataset
    if not os.path.exists(system_dataset):
        try:  
            os.makedirs(system_dataset, mode=0755)
        except Exception as e:  
            print >> sys.stderr, "Unable to create %s: %s" % (system_dataset, e)
            sys.exit(1)

    for ds in system_datasets:
        dataset = "%s/%s" % (system_dataset, ds)
        if not os.path.exists(dataset):
            try:  
                os.makedirs(dataset, mode=0755)
            except Exception as e:  
                print >> sys.stderr, "Unable to create %s: %s" % (dataset, e)
                sys.exit(1)


def set_corefile_sysctl(corepath):
    res = False
    p = pipeopen("/sbin/sysctl kern.corefile='%s'" % corepath)
    p.communicate()
    if p.returncode == 0:
        res = True

    return res


def pick_default_volume():
    volumes = Volume.objects.all()

    for volume in volumes:
        if volume.vol_fstype == 'ZFS' and volume.is_decrypted():
            return volume

    for volume in volumes:
        if volume.vol_fstype == 'UFS' and volume.is_decrypted():
            return volume

    return None


def save_default_volume(volume):
    advanced = Advanced.objects.all()
    if advanced: 
        advanced = advanced[0]
        advanced.adv_system_pool = volume.vol_name
        advanced.save()


def main():

    if (
        hasattr(notifier, 'failover_status') and
        notifier().failover_status() == 'BACKUP'
    ):
        return

    system_datasets = [ 'samba4', 'syslog', 'cores' ]

    volume, basename = get_system_dataset()
    if not volume:
        volume = pick_default_volume()
        if volume:
            save_default_volume(volume)
            basename = "%s/.system" % volume.vol_name

    if not volume:
        print >> sys.stderr, "No system volume configured!"
        sys.exit(1)

    if volume.vol_fstype == 'ZFS' and volume.is_decrypted():
        create_system_datasets_zfs(basename, system_datasets)

    elif volume.vol_fstype == 'UFS' and volume.is_decrypted():
        create_system_datasets_ufs(basename, system_datasets)

    corepath = "/mnt/%s/cores" % basename
    if os.path.exists(corepath):
        set_corefile_sysctl("%s/%%N.core" % corepath)
        os.chmod(corepath, 0775)

if __name__ == '__main__':
    main()
