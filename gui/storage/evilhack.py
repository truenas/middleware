# TODO: This is an evil hack, needs to be refactored into a better shape

from freenasUI.middleware.notifier import notifier

def evil_zvol_destroy(name, iSCSITargetExtent, Disk, destroy=True, WearingSafetyBelt=True):
    reloads = (False, False, False, False)
    disks = Disk.objects.filter(disk_name='zvol/'+name)
    for disk in disks:
        extents = iSCSITargetExtent.objects.filter(iscsi_target_extent_path=str(disk.id))
        if extents.count() > 0:
            if WearingSafetyBelt:
                raise ValueError("EBUSY")
            extents.delete()
            reloads = (False, False, False, True)

    if destroy:
        retval = notifier().destroy_zfs_vol(name)
    else:
        retval = "Not destroyed"

    if WearingSafetyBelt:
        return retval
    else:
        return reloads

