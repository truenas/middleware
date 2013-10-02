import logging
import os
import platform
import time

from django.utils.translation import ugettext as _

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

JAILS_INDEX = "http://cdn.freenas.org"
EXTRACT_TARBALL_STATUS_FILE = "/var/tmp/status"

def get_jails_index(release=None, arch=None):
    global JAILS_INDEX

    if arch is None:
        arch = platform.architecture()
        if arch[0] == '64bit':
            arch = 'x64'
        else:
            arch = 'x32'

    if release is None:
        release = "latest"

    index = "%s/%s/RELEASE/%s/jails" % (
        JAILS_INDEX, release, arch
    )

    return index

def guess_ipv4_addresses():
    high_ipv4 = None
    st_ipv4_network = None

    jc = None
    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        st_ipv4_network = sipcalc_type(jc.jc_ipv4_network)
    except Exception as e:
        log.debug("Exception caught: %s", e)

    #
    # If a jails configuration exists (as it should),
    # create sipcalc objects
    #
    if st_ipv4_network:
        high_ipv4 = sipcalc_type("%s/%d" % (
            jc.jc_ipv4_network_start,
            st_ipv4_network.network_mask_bits
        ))

    #
    # Attempt to determine the primary interface network.
    # This is done so that we don't set a bridge address
    # (we leave it blank, in which case the Warden will
    # figure out the default gateway and set that up inside
    # the jail if on the same network as the host).
    #
    st_host_ipv4_network = None
    try:
        iface = notifier().guess_default_interface()
        st_ha = sipcalc_type(iface=iface)
        if not st_ha.is_ipv4():
            st_host_ipv4_network = None
        else:
            st_host_ipv4_network = sipcalc_type("%s/%d" % (
                st_ha.network_address, st_ha.network_mask_bits
            ))
    except Exception as e:
        log.debug("Exception caught: %s", e)

    #
    # Be extra careful, if no start and end addresses
    # are configured, take the first network address
    # and add 25 to it.
    #
    if not high_ipv4 and st_ipv4_network:
        high_ipv4 = sipcalc_type("%s/%d" % (
            st_ipv4_network.usable_range[0],
            st_ipv4_network.network_mask_bits,
        ))
        high_ipv4 += 25

    try:
        wlist = warden.Warden().list()
    except:
        wlist = []

    for wj in wlist:
        wo = warden.WardenJail(**wj)
        st_ipv4 = None

        #
        # This figures out the highest IP address currently in use
        #

        if wo.ipv4:
            st_ipv4 = sipcalc_type(wo.ipv4)

        if st_ipv4 and st_ipv4_network is not None:
            if st_ipv4_network.in_network(st_ipv4):
                if st_ipv4 > high_ipv4:
                    high_ipv4 = st_ipv4

    if high_ipv4 is None and st_ipv4_network is not None:
        high_ipv4 = sipcalc_type("%s/%d" % (
            st_ipv4_network.usable_range[0],
            st_ipv4_network.network_mask_bits,
        ))

    elif high_ipv4 is not None and st_ipv4_network is not None:
        high_ipv4 += 1
        if not st_ipv4_network.in_network(high_ipv4):
            high_ipv4 = None

    #
    # If a network is configured for jails, and it is NOT on
    # the same network as the host, setup a bridge address.
    # (This will be the default gateway of the jail).
    #
    bridge_ipv4 = None
    if st_ipv4_network is not None and not st_host_ipv4_network:
        bridge_ipv4 = sipcalc_type("%s/%d" % (
            st_ipv4_network.usable_range[0],
            st_ipv4_network.network_mask_bits,
        ))

    return {
        'high_ipv4': high_ipv4,
        'bridge_ipv4': bridge_ipv4
    }

def guess_ipv6_addresses():
    high_ipv6 = None
    st_ipv6_network = None

    jc = None
    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        st_ipv6_network = sipcalc_type(jc.jc_ipv6_network)
    except Exception as e:
        log.debug("Exception caught: %s", e)

    #
    # If a jails configuration exists (as it should),
    # create sipcalc objects
    #
    if st_ipv6_network:
        high_ipv6 = sipcalc_type("%s/%d" % (
            jc.jc_ipv6_network_start,
            st_ipv6_network.prefix_length
        ))

    if not high_ipv6 and st_ipv6_network:
        high_ipv6 = sipcalc_type("%s/%d" % (
            st_ipv6_network.network_range[0],
            st_ipv6_network.prefix_length,
        ))
        high_ipv6 += 25

    #
    # Attempt to determine the primary interface network.
    # This is done so that we don't set a bridge address
    # (we leave it blank, in which case the Warden will
    # figure out the default gateway and set that up inside
    # the jail if on the same network as the host).
    #
    st_host_ipv6_network = None
    try:
        iface = notifier().guess_default_interface()
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

    try:
        wlist = warden.Warden().list()
    except:
        wlist = []

    for wj in wlist:
        wo = warden.WardenJail(**wj)
        st_ipv6 = None

        #
        # This figures out the highest IP address currently in use
        #

        if wo.ipv6:
            st_ipv6 = sipcalc_type(wo.ipv6)

        if st_ipv6 and st_ipv6_network is not None:
            if st_ipv6_network.in_network(st_ipv6):
                if st_ipv6 > high_ipv6:
                    high_ipv6 = st_ipv6

    if high_ipv6 is None and st_ipv6_network is not None:
        high_ipv6 = sipcalc_type("%s/%d" % (
            st_ipv6_network.network_range[0],
            st_ipv6_network.prefix_length,
        ))

    elif high_ipv6 is not None and st_ipv6_network is not None:
        high_ipv6 += 1
        if not st_ipv6_network.in_network(high_ipv6):
            high_ipv6 = None

    #
    # If a network is configured for jails, and it is NOT on
    # the same network as the host, setup a bridge address.
    # (This will be the default gateway of the jail).
    #
    bridge_ipv6 = None
    if st_ipv6_network is not None:
        bridge_ipv6 = sipcalc_type("%s/%d" % (
            st_ipv6_network.network_range[0],
            st_ipv6_network.prefix_length,
        ))

    return {
        'high_ipv6': high_ipv6,
        'bridge_ipv6': bridge_ipv6
    }

def ping_host(host, ping6=False):
    cmd = "/sbin/ping -q -o %s" % host
    if ping6:
        cmd = "/sbin/ping6 -q -o %s" % host

    p = pipeopen(cmd)

    t = time.time()
    timeout = t + 5

    while t <= timeout:
        if p.poll() == 0:
            break

        time.sleep(1)
        t = time.time()

    if p.returncode != 0:
        return False

    return True

def get_available_ipv4(ipv4_initial):
    addr = ipv4_initial

    mask = 0
    try:
        mask = int(str(addr).split('/')[1])
        if not mask:  
            mask = 24
     
    except:
        mask = 24

    i = 0
    naddrs = 2**mask

    while i <= naddrs:
        if not addr:
            break

        if ping_host(str(addr).split('/')[0]):
            addr += 1
        else:
            break

        i += 1

    return addr

def get_available_ipv6(ipv6_initial):
    addr = ipv6_initial

    mask = 0
    try:
        mask = int(str(addr).split('/')[1])
        if not mask:  
            mask = 64
     
    except:
        mask = 64

    i = 0
    naddrs = 2**mask

    while i <= naddrs:
        if not addr:
            break

        if ping_host(str(addr).split('/')[0], ping6=True):
            addr += 1
        else:
            break

        i += 1

    return addr

def guess_addresses():
    addresses = {
        'high_ipv4': None,
        'high_ipv6': None,
        'bridge_ipv4': None,
        'bridge_ipv6': None
    }

    ipv4_addresses = guess_ipv4_addresses()
    high_ipv4 = ipv4_addresses['high_ipv4']
    bridge_ipv4 = ipv4_addresses['bridge_ipv4']

    ipv4_initial = None
    if high_ipv4:
        ipv4_initial = high_ipv4
    elif bridge_ipv4:
        ipv4_initial = bridge_ipv4

    if ipv4_initial:
        ipv4_addr = get_available_ipv4(ipv4_initial)
        if high_ipv4:
            addresses['high_ipv4'] = ipv4_addr
        elif bridge_ipv4:
            addresses['bridge_ipv4'] = ipv4_addr

    ipv6_addresses = guess_ipv6_addresses()
    high_ipv6 = ipv6_addresses['high_ipv6']
    bridge_ipv6 = ipv6_addresses['bridge_ipv6']

    ipv6_initial = None
    if high_ipv6:
        ipv6_initial = high_ipv6
    elif bridge_ipv6:
        ipv4_initial = bridge_ipv6

    if ipv6_initial:
        ipv6_addr = get_available_ipv6(ipv6_initial)
        if high_ipv6:
            addresses['high_ipv6'] = ipv6_addr
        elif bridge_ipv6:
            addresses['bridge_ipv6'] = ipv6_addr

    return addresses


def new_default_plugin_jail(basename):
    addrs = guess_addresses()
    if not addrs['high_ipv4']:
        raise MiddlewareError(_("Unable to determine IPv4 for plugin"))

    jailname = None
    for i in xrange(1, 1000):
        tmpname = "%s_%d" % (basename, i)
        jails = Jails.objects.filter(jail_host=tmpname)
        if not jails:
            jailname = tmpname
            break

    w = warden.Warden()

    jc = JailsConfiguration.objects.order_by("-id")[0]
    logfile = "%s/warden.log" % jc.jc_path

    template_flags = 0
    template_create_args = {}

    template = JailTemplate.objects.get(jt_name='pluginjail')
    template_create_args['nick'] = template.jt_name
    template_create_args['tar'] = template.jt_url
    template_create_args['flags'] = warden.WARDEN_TEMPLATE_FLAGS_CREATE | \
        warden.WARDEN_TEMPLATE_CREATE_FLAGS_NICK | \
        warden.WARDEN_TEMPLATE_CREATE_FLAGS_TAR

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
        try:
            cf = open(createfile, "a+")
            cf.close()
            w.template(**template_create_args)

        except Exception as e:
            if os.path.exists(createfile):
                os.unlink(createfile)
            raise MiddlewareError(e.message)

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
        w.create(
            jail=jailname,
            ipv4=addrs['high_ipv4'],
            flags=(
                warden.WARDEN_CREATE_FLAGS_LOGFILE |
                warden.WARDEN_CREATE_FLAGS_TEMPLATE |
                warden.WARDEN_CREATE_FLAGS_VANILLA |
                warden.WARDEN_CREATE_FLAGS_SYSLOG |
                warden.WARDEN_CREATE_FLAGS_IPV4
            ),
            template='pluginjail',
            logfile=logfile,
        )
    except Exception, e:
        raise MiddlewareError(_("Failed to install plugin: %s") % e)
    w.auto(jail=jailname)
    w.set(
        jail=jailname,
        flags=(
            warden.WARDEN_SET_FLAGS_VNET_ENABLE
        )
    )
    w.start(jail=jailname)
    return Jails.objects.get(jail_host=jailname)


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
    for i in xrange(2, 100):
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
        raise MiddlewareError(_("Failed to create dataset %s: %s") % (
            name,
            err,
        ))

    try:
        jail = JailsConfiguration.objects.latest('id')
    except JailsConfiguration.DoesNotExist:
        jail = JailsConfiguration()
    jail.jc_path = "/mnt/%s" % name
    jail.save()
