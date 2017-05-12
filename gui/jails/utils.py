import logging
import os
import platform
import shutil
import time

from django.utils.translation import ugettext as _

from freenasUI.account.models import bsdUsers
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common import warden
from freenasUI.jails.models import (
    Jails,
    JailsConfiguration,
    JailTemplate
)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.zfs import list_datasets
from freenasUI.storage.models import Volume

log = logging.getLogger('jails.utils')

JAILS_INDEX = "http://download.freenas.org"
EXTRACT_TARBALL_STATUS_FILE = "/var/tmp/status"


#
# get_jails_index()
#
# Get the proper CDN path for jail tarballs
#
def get_jails_index(release=None, arch=None):
    global JAILS_INDEX

    if arch is None:
        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x86'

    if release is None:
        release = "latest"

    index = "%s/%s/RELEASE/%s/jails" % (
        JAILS_INDEX, release, arch
    )

    return index


#
# ping_host()
#
# Check if a host is alive. For IPv4, we timeout after tseconds.
# IPv6 ping does not have the timeout option, so we poll for tseconds,
# then kill the process if a reply is not received.
#
def ping_host(host, ping6=False):
    tseconds = 2

    cmd = "/sbin/ping -q -t %d -o %s" % (tseconds, host)
    if ping6:
        cmd = "/sbin/ping6 -q -o %s -c 1" % host

    p = pipeopen(cmd)

    t = time.time()
    timeout = t + tseconds

    while t <= timeout:
        if p.poll() == 0:
            break

        time.sleep(1)
        t = time.time()

    if p.returncode != 0:
        try:
            p.terminate()
        except:
            pass
        return False

    return True


#
# get_ipv4_exclude_list()
#
# Get a dictionary of all IPv4 addresses currently in use by the warden,
# even if the jail is not running so we can skip over them when probing
# for an address.
#
def get_ipv4_exclude_dict():
    ipv4_exclude_dict = {}

    w = warden.Warden()
    jails = w.cached_list()
    if not jails:
        return ipv4_exclude_dict

    for j in jails:
        mask = 24
        if j['ipv4']:
            parts = j['ipv4'].split('/')
            if len(parts) == 2:
                mask = int(parts[1])
            sc = sipcalc_type("%s/%d" % (
                parts[0],
                mask
            ))
            ipv4_exclude_dict[str(sc)] = sc

        if j['bridge_ipv4']:
            parts = j['bridge_ipv4'].split('/')
            if len(parts) == 2:
                try:
                    mask = int(parts[1])
                except ValueError:
                    pass
            sc = sipcalc_type("%s/%d" % (
                parts[0],
                mask
            ))
            ipv4_exclude_dict[str(sc)] = sc

        if j['alias_ipv4']:
            amask = mask
            aliases = j['alias_ipv4'].split(',')
            for a in aliases:
                parts = a.split('/')
                if len(parts) == 2:
                    amask = int(parts[1])
                sc = sipcalc_type("%s/%d" % (
                    parts[0],
                    amask
                ))
                ipv4_exclude_dict[str(sc)] = sc

        if j['alias_bridge_ipv4']:
            amask = mask
            aliases = j['alias_bridge_ipv4'].split(',')
            for a in aliases:
                parts = a.split('/')
                if len(parts) == 2:
                    amask = int(parts[1])
                sc = sipcalc_type("%s/%d" % (
                    parts[0],
                    amask
                ))
                ipv4_exclude_dict[str(sc)] = sc

    return ipv4_exclude_dict


#
# get_ipv6_exclude_list()
#
# Get a dictionary of all IPv6 addresses currently in use by the warden,
# even if the jail is not running so we can skip over them when probing
# for an address.
#
def get_ipv6_exclude_dict():
    ipv6_exclude_dict = {}

    w = warden.Warden()
    jails = w.cached_list()
    if not jails:
        return ipv6_exclude_dict

    for j in jails:
        prefix = 24
        if j['ipv6']:
            parts = j['ipv6'].split('/')
            if len(parts) == 2:
                prefix = int(parts[1])
            sc = sipcalc_type("%s/%d" % (
                parts[0],
                prefix
            ))
            ipv6_exclude_dict[str(sc)] = sc

        if j['bridge_ipv6']:
            parts = j['ipv6'].split('/')
            if len(parts) == 2:
                prefix = int(parts[1])
            sc = sipcalc_type("%s/%d" % (
                parts[0],
                prefix
            ))
            ipv6_exclude_dict[str(sc)] = sc

        if j['alias_ipv6']:
            aprefix = prefix
            aliases = j['alias_ipv6'].split(',')
            for a in aliases:
                parts = a.split('/')
                if len(parts) == 2:
                    aprefix = int(parts[1])
                sc = sipcalc_type("%s/%d" % (
                    parts[0],
                    aprefix
                ))
                ipv6_exclude_dict[str(sc)] = sc

        if j['alias_bridge_ipv6']:
            aprefix = prefix
            aliases = j['alias_bridge_ipv6'].split(',')
            for a in aliases:
                parts = a.split('/')
                if len(parts) == 2:
                    aprefix = int(parts[1])
                sc = sipcalc_type("%s/%d" % (
                    parts[0],
                    aprefix
                ))
                ipv6_exclude_dict[str(sc)] = sc

    return ipv6_exclude_dict


#
# get_available_ipv4()
#
# Find an IPv4 address in a given range. If no end address
# is provided, use the netmask to determine how many addresses
# to probe. If not netmask is provided, assume /24.
#
def get_available_ipv4(ipv4_start, ipv4_end=None, ipv4_exclude_dict=None):
    available_ipv4 = None
    addr = ipv4_start

    if not ipv4_end:
        mask = 0
        try:
            mask = int(str(addr).split('/')[1])
            if not mask:
                mask = 24
        except:
            mask = 24

        naddrs = 2 ** mask

    else:
        naddrs = int(ipv4_end) - int(ipv4_start)

    i = 0
    while i <= naddrs:
        if not addr:
            break

        if ipv4_exclude_dict and str(addr) in ipv4_exclude_dict:
            addr += 1
            i += 1
            continue

        if ping_host(str(addr).split('/')[0]):
            addr += 1
            i += 1
            continue

        else:
            available_ipv4 = addr
            break

        i += 1

    return available_ipv4


#
# get_available_ipv6()
#
# Find an IPv6 address in a given range. If no end address
# is provided, use the prefix to determine how many addresses
# to probe. If not prefix is provided, assume /64.
#
def get_available_ipv6(ipv6_start, ipv6_end=None, ipv6_exclude_dict=None):
    available_ipv6 = None
    addr = ipv6_start

    if not ipv6_end:
        prefix = 0
        try:
            prefix = int(str(addr).split('/')[1])
            if not prefix:
                prefix = 64

        except:
            prefix = 64

        naddrs = 2 ** prefix

    else:
        naddrs = int(ipv6_end) - int(ipv6_start)

    i = 0
    while i <= naddrs:
        if not addr:
            break

        if ipv6_exclude_dict and str(addr) in ipv6_exclude_dict:
            addr += 1
            i += 1
            continue

        if ping_host(str(addr).split('/')[0], ping6=True):
            addr += 1
            i += 1
            continue

        else:
            available_ipv6 = addr
            break

        i += 1

    return available_ipv6


def get_jail_ipv4_network():
    jail_ipv4_network = None

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv4_network = sipcalc_type(jc.jc_ipv4_network)

    except:
        jail_ipv4_network = None

    return jail_ipv4_network


def get_jail_ipv4_network_start():
    jail_ipv4_network_start = None
    jail_ipv4_network = get_jail_ipv4_network()

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv4_network_start = sipcalc_type("%s/%d" % (
            jc.jc_ipv4_network_start.split('/')[0],
            jail_ipv4_network.network_mask_bits
        ))

    except:
        jail_ipv4_network_start = None

    return jail_ipv4_network_start


def get_jail_ipv4_network_end():
    jail_ipv4_network_end = None
    jail_ipv4_network = get_jail_ipv4_network()

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv4_network_end = sipcalc_type("%s/%d" % (
            jc.jc_ipv4_network_end.split('/')[0],
            jail_ipv4_network.network_mask_bits
        ))

    except:
        jail_ipv4_network_end = None

    return jail_ipv4_network_end


def get_jail_ipv6_network():
    jail_ipv6_network = None

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv6_network = sipcalc_type(jc.jc_ipv6_network)

    except:
        jail_ipv6_network = None

    return jail_ipv6_network


def get_jail_ipv6_network_start():
    jail_ipv6_network_start = None
    jail_ipv6_network = get_jail_ipv6_network()

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv6_network_start = sipcalc_type("%s/%d" % (
            jc.jc_ipv6_network_start.split('/')[0],
            jail_ipv6_network.prefix_length
        ))

    except:
        jail_ipv6_network_start = None

    return jail_ipv6_network_start


def get_jail_ipv6_network_end():
    jail_ipv6_network_end = None
    jail_ipv6_network = get_jail_ipv6_network()

    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jail_ipv6_network_end = sipcalc_type("%s/%d" % (
            jc.jc_ipv6_network_end.split('/')[0],
            jail_ipv6_network.prefix_length
        ))

    except:
        jail_ipv6_network_end = None

    return jail_ipv6_network_end


#
# get_ipv4_address()
#
# Get the configured jail IPv4 network, if it doesn't have a start or stop
# address, fill them in, then probe the range for first available address.
#
def get_ipv4_address():
    ipv4_addr = None

    st_ipv4_network = get_jail_ipv4_network()
    if st_ipv4_network:
        st_ipv4_network_start = get_jail_ipv4_network_start()
        if not st_ipv4_network_start:
            st_ipv4_network_start = sipcalc_type("%s/%d" % (
                st_ipv4_network.usable_range[0],
                st_ipv4_network.network_mask_bits
            ))

        st_ipv4_network_end = get_jail_ipv4_network_end()
        if not st_ipv4_network_end:
            st_ipv4_network_end = sipcalc_type("%s/%d" % (
                st_ipv4_network.usable_range[1],
                st_ipv4_network.network_mask_bits
            ))

        ipv4_addr = get_available_ipv4(
            st_ipv4_network_start,
            st_ipv4_network_end,
            get_ipv4_exclude_dict()
        )

    return ipv4_addr


#
# get_ipv6_address()
#
# Get the configured jail IPv6 network, if it doesn't have a start or stop
# address, fill them in, then probe the range for first available address.
#
def get_ipv6_address():
    ipv6_addr = None

    st_ipv6_network = get_jail_ipv6_network()
    if st_ipv6_network:
        st_ipv6_network_start = get_jail_ipv6_network_start()
        if not st_ipv6_network_start:
            st_ipv6_network_start = sipcalc_type("%s/%d" % (
                st_ipv6_network.network_range[0],
                st_ipv6_network.prefix_length
            ))

        st_ipv6_network_end = get_jail_ipv6_network_end()
        if not st_ipv6_network_end:
            st_ipv6_network_end = sipcalc_type("%s/%d" % (
                st_ipv6_network.network_range[1],
                st_ipv6_network.prefix_length
            ))

        ipv6_addr = get_available_ipv6(
            st_ipv6_network_start,
            st_ipv6_network_end,
            get_ipv6_exclude_dict()
        )

    return ipv6_addr


#
# get_host_ipv4_network()
#
# Attempt to determine the primary interface network. This is done so that we
# don't set a bridge address (we leave it blank, in which case the Warden
# will figure out the default gateway and set tha tup inside the jail if
# on the same network as the host).
#
def get_host_ipv4_network():
    st_host_ipv4_network = None

    try:
        iface = notifier().get_default_ipv4_interface()
        st_ha = sipcalc_type(iface=iface)
        if not st_ha.is_ipv4():
            st_host_ipv4_network = None
        else:
            st_host_ipv4_network = sipcalc_type("%s/%d" % (
                st_ha.network_address, st_ha.network_mask_bits
            ))
    except Exception as e:
        log.debug("Exception caught: %s", e)

    return st_host_ipv4_network


#
# get_host_ipv6_network()
#
# Attempt to determine the primary interface network. This is done so that we
# don't set a bridge address (we leave it blank, in which case the Warden
# will figure out the default gateway and set tha tup inside the jail if
# on the same network as the host).
#
def get_host_ipv6_network():
    st_host_ipv6_network = None

    try:
        iface = notifier().get_default_ipv6_interface()
        st_ha = sipcalc_type(iface=iface)
        if not st_ha.is_ipv6():
            st_host_ipv6_network = None
        else:
            st_host_ipv6_network = sipcalc_type("%s/%d" % (
                st_ha.network_range[0],
                st_ha.prefix_length,
            ))
    except Exception as e:
        log.debug("Exception caught: %s", e)

    return st_host_ipv6_network


def guess_ipv4_addresses():
    addresses = {
        'high_ipv4': None,
        'bridge_ipv4': None
    }

    ipv4_addr = get_ipv4_address()
    ipv4_jail_network = get_jail_ipv4_network()

    if ipv4_addr:
        addresses['high_ipv4'] = ipv4_addr

    if (ipv4_jail_network and ipv4_addr) and (not ipv4_jail_network.in_network(ipv4_addr)):
        try:
            addresses['bridge_ipv4'] = sipcalc_type("%s/%d" % (
                ipv4_jail_network.usable_range[0],
                ipv4_jail_network.network_mask_bits,
            ))
        except Exception as e:
            log.debug("guess_addresses: %s", e)
            return addresses

    return addresses


def guess_ipv6_addresses():
    addresses = {
        'high_ipv6': None,
        'bridge_ipv6': None
    }

    ipv6_addr = get_ipv6_address()
    ipv6_jail_network = get_jail_ipv6_network()

    if ipv6_addr:
        addresses['high_ipv6'] = ipv6_addr

    if (ipv6_jail_network and ipv6_addr) and (not ipv6_jail_network.in_network(ipv6_addr)):
        try:
            addresses['bridge_ipv6'] = sipcalc_type("%s/%d" % (
                ipv6_jail_network.network_range[0],
                ipv6_jail_network.prefix_length,
            ))
        except Exception as e:
            log.debug("guess_addresses: %s", e)
            return addresses

    return addresses


#
# guess_addresses()
#
# Figure out the next IPv4 and IPv6 addresses available (if any).
# If a bridge address is necessary, figure that as well
#
def guess_addresses():
    addresses = {}

    ipv4_addresses = guess_ipv4_addresses()
    addresses.update(ipv4_addresses)

    ipv6_addresses = guess_ipv6_addresses()
    addresses.update(ipv6_addresses)

    return addresses


def new_default_plugin_jail(basename):
    from freenasUI.jails.forms import generate_randomMAC, is_jail_mac_duplicate
    jc = JailsConfiguration.objects.order_by("-id")[0]
    logfile = "%s/warden.log" % jc.jc_path

    if not jc.jc_ipv4_dhcp or not jc.jc_ipv6_autoconf:
        addrs = guess_addresses()

    if not jc.jc_ipv4_dhcp:
        if not addrs['high_ipv4']:
            raise MiddlewareError(_("Unable to determine IPv4 for plugin"))

    if (jc.jc_ipv6_autoconf or jc.jc_ipv6_network):
        if not jc.jc_ipv6_autoconf:
            if not addrs['high_ipv6']:
                raise MiddlewareError(_("Unable to determine IPv6 for plugin"))

    jailname = None
    for i in range(1, 1000):
        tmpname = "%s_%d" % (basename, i)
        jails = Jails.objects.filter(jail_host=tmpname)
        if not jails:
            jailname = tmpname
            break

    w = warden.Warden()
    template_create_args = {}

    template = JailTemplate.objects.get(jt_name='pluginjail')
    template_create_args['nick'] = template.jt_name
    template_create_args['tar'] = template.jt_url
    template_create_args['flags'] = warden.WARDEN_TEMPLATE_FLAGS_CREATE | \
        warden.WARDEN_TEMPLATE_CREATE_FLAGS_NICK | \
        warden.WARDEN_TEMPLATE_CREATE_FLAGS_TAR
    if template.jt_mtree:
        template_create_args['mtree'] = template.jt_mtree
        template_create_args['flags'] = template_create_args['flags'] | \
            warden.WARDEN_TEMPLATE_CREATE_FLAGS_MTREE

    template = None
    template_list_flags = {}
    template_list_flags['flags'] = warden.WARDEN_TEMPLATE_FLAGS_LIST
    templates = w.template(**template_list_flags)
    for t in templates:
        if t['nick'] == template_create_args['nick']:
            template = t
            break

    os.environ['EXTRACT_TARBALL_STATUSFILE'] = warden.WARDEN_EXTRACT_STATUS_FILE
    createfile = "/var/tmp/.templatecreate"
    if not template:

        # If for some reason warden does not list the template but the path
        # exists, we shall try to nuke it
        template_path = '{}/.warden-template-pluginjail'.format(jc.jc_path)
        if os.path.exists(template_path):
            try:
                notifier().destroy_zfs_dataset(template_path.replace('/mnt/', ''))
            except:
                pass
            try:
                shutil.rmtree(template_path)
            except OSError:
                pass

        try:
            cf = open(createfile, "a+")
            cf.close()
            w.template(**template_create_args)

        except Exception as e:
            if os.path.exists(createfile):
                os.unlink(createfile)
            raise MiddlewareError(e)

        template_list_flags = {}
        template_list_flags['flags'] = warden.WARDEN_TEMPLATE_FLAGS_LIST
        templates = w.template(**template_list_flags)
        for t in templates:
            if t['nick'] == template_create_args['nick']:
                template = t
                break

    if not template:
        raise MiddlewareError(_('Unable to find template!'))

    try:
        high_ipv4 = "DHCP"
        if not jc.jc_ipv4_dhcp:
            high_ipv4 = addrs['high_ipv4']

        high_ipv6 = "AUTOCONF"
        if not jc.jc_ipv6_autoconf:
            high_ipv6 = addrs['high_ipv6']

        create_args = {
            'jail': jailname,
            'ipv4': high_ipv4,
            'ipv6': high_ipv6,
            'flags': (
                warden.WARDEN_CREATE_FLAGS_LOGFILE |
                warden.WARDEN_CREATE_FLAGS_TEMPLATE |
                warden.WARDEN_CREATE_FLAGS_VANILLA |
                warden.WARDEN_CREATE_FLAGS_SYSLOG |
                warden.WARDEN_CREATE_FLAGS_IPV4 |
                warden.WARDEN_CREATE_FLAGS_IPV6
            ),
            'template': 'pluginjail',
            'logfile': logfile
        }

        w.create(**create_args)

    except Exception as e:
        raise MiddlewareError(_("Failed to install plugin: %s") % e)

    jaildir = "%s/%s" % (jc.jc_path, jailname)
    with open('%s/.plugins/PLUGIN' % jaildir, 'w') as f:
        f.close()

    w.auto(jail=jailname)

    # Make sure we generate an unique mac address for the plugin jail
    while True:
        mac = generate_randomMAC()
        if not is_jail_mac_duplicate(mac):
            break
    w.set(
        jail=jailname,
        mac=mac,
        flags=warden.WARDEN_SET_FLAGS_MAC,
    )
    # Setting vnet and mac at the same time seems to confuse Warden wrapper
    w.set(
        jail=jailname,
        flags=warden.WARDEN_SET_FLAGS_VNET_ENABLE,
    )
    w.start(jail=jailname)

    obj = Jails.objects.get(jail_host=jailname)
    add_media_user_and_group(obj.jail_path)
    return obj


def jail_path_configured():
    """
    Check if there is the jail system is configured
    by looking at the JailsConfiguration model and
    jc_path field

    :Returns: boolean
    """
    try:
        jc = JailsConfiguration.objects.latest('id')
    except JailsConfiguration.DoesNotExist:
        jc = None

    return jc and jc.jc_path and os.path.exists(jc.jc_path)


def jail_auto_configure():
    import platform

    """
    Auto configure the jail settings

    The first ZFS volume found will be selected.
    A dataset called jails will be created, if it already exists then
    append "_N" where N 2..100 until a dataset is not found.
    """

    volume = Volume.objects.filter(vol_fstype='ZFS')
    if not volume.exists():
        raise MiddlewareError(_("You need to create a ZFS volume to proceed!"))

    volume = volume[0]
    basename = "%s/jails" % volume.vol_name

    name = basename
    for i in range(2, 100):
        datasets = list_datasets(
            path="/mnt/%s" % name,
            recursive=False,
        )
        if not datasets:
            break
        else:
            name = "%s_%d" % (basename, i)
    rv, err = notifier().create_zfs_dataset(name)
    if rv != 0:
        raise MiddlewareError(_("Failed to create dataset %(name)s: %(error)s") % {
            'name': name,
            'error': err,
        })

    try:
        jail = JailsConfiguration.objects.latest('id')
    except JailsConfiguration.DoesNotExist:
        jail = JailsConfiguration()
    jail.jc_path = "/mnt/%s" % name
    jail.save()

    w = warden.Warden()
    w.wtmp = jail.jc_path
    w.jdir = jail.jc_path
    w.release = platform.release().strip()
    w.save()


def add_media_user_and_group(jail_path):
    if not jail_path or not os.path.exists(jail_path):
        return False

    try:
        media_user = bsdUsers.objects.filter(bsdusr_username='media')[0]
    except:
        log.debug('add_media_user_and_group: unable to find media user')
        return False

    if not media_user.bsdusr_group:
        log.debug('add_media_user_and_group: media user has no group')
        return False

    groupdel_cmd = "/usr/sbin/pw groupdel '%s'" % media_user.bsdusr_group.bsdgrp_group
    chroot_groupdel_cmd = "/usr/sbin/chroot '%s' %s" % (jail_path, groupdel_cmd)

    groupadd_cmd = "/usr/sbin/pw groupadd '%s' -g '%d'" % (
        media_user.bsdusr_group.bsdgrp_group,
        media_user.bsdusr_group.bsdgrp_gid)
    chroot_groupadd_cmd = "/usr/sbin/chroot '%s' %s" % (jail_path, groupadd_cmd)

    userdel_cmd = "/usr/sbin/pw userdel '%s'" % media_user.bsdusr_username
    chroot_userdel_cmd = "/usr/sbin/chroot '%s' %s" % (jail_path, userdel_cmd)

    useradd_cmd = "/usr/sbin/pw useradd '%s' -u '%d' -g '%s'" % (
        media_user.bsdusr_username,
        media_user.bsdusr_uid,
        media_user.bsdusr_group.bsdgrp_group)
    chroot_useradd_cmd = "/usr/sbin/chroot '%s' %s" % (jail_path, useradd_cmd)

    p = pipeopen(chroot_groupadd_cmd, allowfork=True, close_fds=True)
    out = p.communicate()
    if p.returncode != 0:
        log.debug('add_media_user_and_group: failed to create media group: %s', out)
        pipeopen(chroot_groupdel_cmd, allowfork=True, close_fds=True).communicate()
        return False

    p = pipeopen(chroot_useradd_cmd, allowfork=True, close_fds=True)
    out = p.communicate()
    if p.returncode != 0:
        log.debug('add_media_user_and_group: failed to create media user: %s', out)
        pipeopen(chroot_userdel_cmd, allowfork=True, close_fds=True).communicate()
        return False

    return True
