#!/usr/bin/env python
"""
Autotuning program.

Garrett Cooper, December 2011

Example:
    autotune.py --conf loader \
                --kernel-reserved=2147483648 \
                --userland-reserved=4294967296
"""


import argparse
import platform
import re
import shlex
import subprocess
import sys

sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings
from django.core.management import setup_environ

setup_environ(settings)

from freenasUI.system.models import Advanced, Sysctl, Tunable

MB = 1024 * 1024
GB = 1024 * MB


# 32, 64, etc.
ARCH_WIDTH = int(platform.architecture()[0].replace('bit', ''))

LOADER_CONF = '/boot/loader.conf'
SYSCTL_CONF = '/etc/sysctl.conf'

# We need 3GB(x86)/6GB(x64) on a properly spec'ed system for our middleware
# for the system to function comfortably, with a little kernel memory to spare
# for other things.
if ARCH_WIDTH == 32:

    DEFAULT_USERLAND_RESERVED_MEM = USERLAND_RESERVED_MEM = int(1.00 * GB)

    DEFAULT_KERNEL_RESERVED_MEM = KERNEL_RESERVED_MEM = 384 * MB

    MIN_KERNEL_RESERVED_MEM = 64 * MB

    MIN_ZFS_RESERVED_MEM = 512 * MB

elif ARCH_WIDTH == 64:

    DEFAULT_USERLAND_RESERVED_MEM = USERLAND_RESERVED_MEM = int(2.25 * GB)

    DEFAULT_KERNEL_RESERVED_MEM = KERNEL_RESERVED_MEM = 768 * MB

    MIN_KERNEL_RESERVED_MEM = 128 * MB

    MIN_ZFS_RESERVED_MEM = 1024 * MB

else:

    sys.exit('Architecture bit-width (%d) not supported' % (ARCH_WIDTH, ))


def popen(cmd):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
    return p.communicate()[0]


def get_interfaces(include_fake=False):

    interfaces = popen('ifconfig -l')

    fake_interfaces = (
                       'ipfw',
                       'lo',
                       'pflog',
                       'pfsync',
                      )

    interfaces = interfaces.split()

    if include_fake:
        return interfaces
    return filter(lambda i: not re.match('^(%s)\d+$'
                                         % ('|'.join(fake_interfaces), ), i),
                                         interfaces)


def sysctl(oid):
    """Quick and dirty means of doing sysctl -n"""
    return popen('sysctl -n %s' % (oid, ))


def sysctl_int(oid):
    """... on an integer OID"""
    return int(sysctl(oid))


HW_PHYSMEM = sysctl_int('hw.physmem')

DEF_KNOBS = {
    'loader': {
        'kern.ipc.nmbclusters',
        'vm.kmem_size',
        'vfs.zfs.arc_max',
    },
    'sysctl': {
        'kern.ipc.maxsockbuf',
        'net.inet.tcp.recvbuf_max',
        'net.inet.tcp.sendbuf_max',
    },
}


def guess_kern_ipc_maxsockbuf():
    """Maximum socket buffer.

    Higher -> better throughput, but greater tha likelihood of wasted bandwidth
    and memory use/chance for starvation with a larger number of connections.
    """
    # 9.x defaults
    return 2 * MB


# kern.ipc.maxsockets


def guess_kern_ipc_nmbclusters():
    """Non-jumbo frame mbuf IPC cluster pool count
    """

    default_mbufs = 5000

    # TODO: need to get better approximations.
    needed_mbufs = {
                    'cxgb' : 40000,
                    'cxgbe': 50000,
                    'igb'  : 20000,
                    'ixgb' : 30000,
                    }

    total_mbufs = 0
    for interface in get_interfaces():
        for driver, mbuf_value in needed_mbufs.iteritems():
            if re.match('^%s\d+$' % (driver, ), interface):
                total_mbufs += mbuf_value
                break
        else:
            total_mbufs += default_mbufs
    return total_mbufs


def guess_kern_ipc_nmbjumbo9():
    """9k jumbo frame mbuf IPC cluster pool count
    """
    # XXX: could be dynamic depending on the number and type of NICs.
    return 25600


# kern.ipc.somaxconn


def guess_kern_maxfiles():
    """Maximum number of files that can be opened on a system

    - Samba sets this to 16k by default to meet a Windows minimum value.
    """
    # XXX: should be dynamically tuned based on the platform profile.
    return 65536


def guess_kern_maxfilesperproc():
    """Maximum number of files that can be opened per process

    - FreeBSD defined ratio is 9:10, but that's with lower limits.
    """
    return int(0.8 * guess_kern_maxfiles())


def guess_net_inet_tcp_recvbuf_max():
    """Maximum size for TCP receive buffers

    See guess_kern_ipc_maxsockbuf().
    """
    return 2 * MB


def guess_net_inet_tcp_sendbuf_max():
    """Maximum size for TCP send buffers

    See guess_kern_ipc_maxsockbuf().
    """
    return 2 * MB


def guess_vm_kmem_size():
    """ Default memory available to the kernel
    """
    return int(0.8 * guess_vm_kmem_size_max())


def guess_vm_kmem_size_max():
    """Maximum usable scratch space for kernel memory
    """
    return int(max(HW_PHYSMEM - USERLAND_RESERVED_MEM,
                   MIN_KERNEL_RESERVED_MEM + MIN_ZFS_RESERVED_MEM))


def guess_vfs_zfs_arc_max():
    """ Maximum usable scratch space for the ZFS ARC in secondary memory

    - See comments for USERLAND_RESERVED_MEM.
    """
    return int(max(HW_PHYSMEM - (USERLAND_RESERVED_MEM + KERNEL_RESERVED_MEM),
                   MIN_ZFS_RESERVED_MEM))


# vfs.zfs.txg.synctime_ms
# vfs.zfs.txg.timeout
# vfs.zfs.vdev.cache.max
# vfs.zfs.vdev.read_gap_limit
# vfs.zfs.vdev.write_gap_limit
# vfs.zfs.write_limit_min
# vfs.zfs.write_limit_max


def main(argv):
    """main"""

    global KERNEL_RESERVED_MEM
    global USERLAND_RESERVED_MEM

    adv = Advanced.objects.order_by('-id')[0]
    if not adv.adv_autotune:
        return

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--conf',
                        default='loader',
                        type=str,
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

    recommendations = dict([
        (knob, str(eval('guess_%s()'
                        % (knob.replace('.', '_'), )), )) for knob in knobs
        ])

    if args.conf == 'loader':
        model = Tunable
        var_field = 'tun_var'
        value_field = 'tun_value'
        comment_field = 'tun_comment'
    elif args.conf == 'sysctl':
        model = Sysctl
        var_field = 'sysctl_mib'
        value_field = 'sysctl_value'
        comment_field = 'sysctl_comment'

    for var, value in recommendations.items():
        qs = model.objects.filter(**{var_field: var})
        if qs.exists() and args.overwrite:
            obj = qs[0]
        elif qs.exists() and not args.overwrite:
            print >> sys.stderr, "skipping", var, "already on db"
            continue
        else:
            obj = model()
        setattr(obj, var_field, var)
        setattr(obj, value_field, value)
        setattr(obj, comment_field, 'Generated by autotune')
        obj.save()


if __name__ == '__main__':
    main(sys.argv[1:])
