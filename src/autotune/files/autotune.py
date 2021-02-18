#!/usr/local/bin/python
"""
Autotuning program.

Garrett Cooper, December 2011

Example:
    autotune.py --conf loader \
                --kernel-reserved=2147483648 \
                --userland-reserved=4294967296
"""


import argparse
import atexit
import os
import shlex
import subprocess
import sys

from middlewared.client import Client

c = Client('ws+unix:///var/run/middlewared-internal.sock')
if not c.call('system.is_enterprise'):
    ENTERPRISE = False
else:
    ENTERPRISE = True
    hardware = c.call('truenas.get_chassis_hardware')
    hardware = hardware.replace('TRUENAS-', '')
    hardware = hardware.split('-')


KiB = 1024 ** 1
MiB = 1024 ** 2
GiB = 1024 ** 3

NO_HASYNC = "/tmp/.sqlite3_ha_skip"


@atexit.register
def cleanup():
    try:
        os.unlink(NO_HASYNC)
    except Exception:
        pass


LOADER_CONF = '/boot/loader.conf'
SYSCTL_CONF = '/etc/sysctl.conf'

# We need 3GB(x86)/6GB(x64) on a properly spec'ed system for our middleware
# for the system to function comfortably, with a little kernel memory to spare
# for other things.
DEFAULT_USERLAND_RESERVED_MEM = USERLAND_RESERVED_MEM = int(2.25 * GiB)

DEFAULT_KERNEL_RESERVED_MEM = KERNEL_RESERVED_MEM = 768 * MiB

MIN_KERNEL_RESERVED_MEM = 128 * MiB

MIN_ZFS_RESERVED_MEM = 1024 * MiB


def popen(cmd):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
    return p.communicate()[0]


def sysctl(oid):
    """Quick and dirty means of doing sysctl -n"""
    return popen('sysctl -n %s' % (oid, ))


def sysctl_int(oid):
    """... on an integer OID"""
    return int(sysctl(oid))


# TrueNAS HA heads may have slighty different available memory
HW_PHYSMEM = sysctl_int('hw.physmem') // 10000000 * 10000000
HW_PHYSMEM_GiB = HW_PHYSMEM / GiB

# If you add a dictionary key here be sure to add it
# as a valid choice to the -c option.
DEF_KNOBS = {
    'loader': {
        'vfs.zfs.dirty_data_max_max',
    },
    'sysctl': {
        'kern.ipc.maxsockbuf',
        'net.inet.tcp.delayed_ack',
        'net.inet.tcp.recvbuf_max',
        'net.inet.tcp.sendbuf_max',
        'vfs.zfs.arc_max',
        'vfs.zfs.l2arc_noprefetch',
        'vfs.zfs.l2arc_write_max',
        'vfs.zfs.l2arc_write_boost',
        'net.inet.tcp.mssdflt',
        'net.inet.tcp.recvspace',
        'net.inet.tcp.sendspace',
        'net.inet.tcp.sendbuf_max',
        'net.inet.tcp.recvbuf_max',
        'net.inet.tcp.sendbuf_inc',
        'net.inet.tcp.recvbuf_inc',
        'vfs.zfs.vdev.async_read_max_active',
        'vfs.zfs.vdev.sync_read_max_active',
        'vfs.zfs.vdev.async_write_max_active',
        'vfs.zfs.vdev.sync_write_max_active',
        'vfs.zfs.zfetch.max_distance',
    },
}


def guess_vfs_zfs_dirty_data_max_max():
    if ENTERPRISE and hardware[0].startswith("M"):
        return 12 * GiB
    else:
        return None


def guess_kern_ipc_maxsockbuf():
    """Maximum socket buffer.

    Higher -> better throughput, but greater the likelihood of wasted bandwidth
    and memory use/chance for starvation with a larger number of connections.
    """
    if HW_PHYSMEM_GiB > 180:
        return 16 * MiB
    elif HW_PHYSMEM_GiB > 84:
        return 8 * MiB
    elif HW_PHYSMEM_GiB > 44:
        return 4 * MiB
    else:
        return 2 * MiB


def guess_net_inet_tcp_delayed_ack():
    """Set the TCP stack to not use delayed ACKs

    """
    return 0


def guess_net_inet_tcp_recvbuf_max():
    """Maximum size for TCP receive buffers

    See guess_kern_ipc_maxsockbuf().
    """
    return 16 * MiB


def guess_net_inet_tcp_sendbuf_max():
    """Maximum size for TCP send buffers

    See guess_kern_ipc_maxsockbuf().
    """
    return 16 * MiB


def guess_vfs_zfs_arc_max():
    """ Maximum usable scratch space for the ZFS ARC in secondary memory

    - See comments for USERLAND_RESERVED_MEM.
    """
    if HW_PHYSMEM_GiB > 200 and ENTERPRISE:
        return int(max(min(int(HW_PHYSMEM * .92),
                       HW_PHYSMEM - (USERLAND_RESERVED_MEM + KERNEL_RESERVED_MEM)),
                       MIN_ZFS_RESERVED_MEM))
    else:
        return int(max(min(int(HW_PHYSMEM * .9),
                       HW_PHYSMEM - (USERLAND_RESERVED_MEM + KERNEL_RESERVED_MEM)),
                       MIN_ZFS_RESERVED_MEM))


def guess_vfs_zfs_l2arc_noprefetch():
    return 0


def guess_vfs_zfs_l2arc_write_max():
    return 10000000


def guess_vfs_zfs_l2arc_write_boost():
    return 40000000


def guess_net_inet_tcp_mssdflt():
    return 1448


def guess_net_inet_tcp_recvspace():
    if HW_PHYSMEM_GiB > 180:
        return 1 * MiB
    elif HW_PHYSMEM_GiB > 84:
        return 512 * KiB
    elif HW_PHYSMEM_GiB > 44:
        return 256 * KiB
    else:
        return 128 * KiB


def guess_net_inet_tcp_sendspace():
    if HW_PHYSMEM_GiB > 180:
        return 1 * MiB
    elif HW_PHYSMEM_GiB > 84:
        return 512 * KiB
    elif HW_PHYSMEM_GiB > 44:
        return 256 * KiB
    else:
        return 128 * KiB


def guess_net_inet_tcp_sendbuf_inc():
    return 16 * KiB


def guess_net_inet_tcp_recvbuf_inc():
    return 512 * KiB


def guess_vfs_zfs_vdev_async_read_max_active():
    if ENTERPRISE and hardware[0] == "Z50":
        return 64
    else:
        return None


def guess_vfs_zfs_vdev_sync_read_max_active():
    if ENTERPRISE and hardware[0] == "Z50":
        return 64
    else:
        return None


def guess_vfs_zfs_vdev_async_write_max_active():
    if ENTERPRISE and hardware[0] == "Z50":
        return 64
    else:
        return None


def guess_vfs_zfs_vdev_sync_write_max_active():
    if ENTERPRISE and hardware[0] == "Z50":
        return 64
    else:
        return None


def guess_vfs_zfs_zfetch_max_distance():
    return 32 * MiB


def main(argv):
    """main"""

    global KERNEL_RESERVED_MEM
    global USERLAND_RESERVED_MEM

    adv = c.call('system.advanced.config')
    if not adv['autotune']:
        return

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--conf',
                        default='loader',
                        type=str,
                        choices=['loader', 'sysctl'],
                        )
    parser.add_argument('-o', '--overwrite',
                        default=False,
                        action="store_true"
                        )
    parser.add_argument('-k', '--kernel-reserved',
                        default=KERNEL_RESERVED_MEM,
                        type=int,
                        )
    parser.add_argument('-u', '--userland-reserved',
                        default=USERLAND_RESERVED_MEM,
                        type=int,
                        )
    args = parser.parse_args()

    knobs = DEF_KNOBS.get(args.conf)
    if not knobs:
        parser.error('Invalid conf specified: %s' % (args.conf, ))

    if args.kernel_reserved < DEFAULT_KERNEL_RESERVED_MEM:
        parser.error('Value specified for --kernel-reserved is < %d'
                     % (DEFAULT_KERNEL_RESERVED_MEM, ))
    KERNEL_RESERVED_MEM = args.kernel_reserved

    if args.userland_reserved < DEFAULT_USERLAND_RESERVED_MEM:
        parser.error('Value specified for --userland-reserved is < %d'
                     % (DEFAULT_USERLAND_RESERVED_MEM, ))
    USERLAND_RESERVED_MEM = args.userland_reserved

    recommendations = {}
    for knob in knobs:
        func = 'guess_%s()' % (knob.replace('.', '_'), )
        retval = eval(func)
        if retval is None:
            continue
        recommendations[knob] = str(retval)

    changed_values = False
    open(NO_HASYNC, 'w').close()
    for var, value in recommendations.items():
        qs = c.call('tunable.query', [('var', '=', var)])
        if qs and not args.overwrite:
            # Already exists and we're honoring the user setting. Move along.
            continue
        if qs:
            obj = qs[0]
            # We bail out here because if we set a value to what the database
            # already has we'll set changed_values = True which will
            # cause ix-loader to reboot the system.
            if obj['type'].lower() == args.conf and obj['value'] == value:
                continue
        else:
            obj = {}
        obj['var'] = var
        obj['value'] = value
        obj['type'] = args.conf.upper()
        obj['comment'] = 'Generated by autotune'
        objid = obj.pop('id', None)
        if objid:
            c.call('tunable.update', objid, obj)
        else:
            c.call('tunable.create', obj)
        # If we got this far, that means the database save went through just
        # fine at least once.
        changed_values = True

    cleanup()
    if changed_values:
        # Informs the caller that a change was made and a reboot is required.
        sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])
