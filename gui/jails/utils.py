import logging
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.common.warden import Warden, WardenJail
from freenasUI.jails.models import JailsConfiguration
from freenasUI.middleware.notifier import notifier

log = logging.getLogger('jails.utils')


def guess_adresses():
    high_ipv4 = None
    high_ipv6 = None

    st_ipv4_network = None
    st_ipv6_network = None

    jc = None
    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        st_ipv4_network = sipcalc_type(jc.jc_ipv4_network)
        st_ipv6_network = sipcalc_type(jc.jc_ipv6_network)
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
    if st_ipv6_network:
        high_ipv6 = sipcalc_type("%s/%d" % (
            jc.jc_ipv6_network_start,
            st_ipv6_network.prefix_length
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

    if not high_ipv6 and st_ipv6_network:
        high_ipv6 = sipcalc_type("%s/%d" % (
            st_ipv6_network.network_range[0],
            st_ipv6_network.prefix_length,
        ))
        high_ipv6 += 25

    try:
        wlist = Warden().list()
    except:
        wlist = []

    for wj in wlist:
        wo = WardenJail(**wj)

        st_ipv4 = None
        st_ipv6 = None

        #
        # This figures out the highest IP address currently in use
        #

        if wo.ipv4:
            st_ipv4 = sipcalc_type(wo.ipv4)
        if wo.ipv6:
            st_ipv6 = sipcalc_type(wo.ipv6)

        if st_ipv4 and st_ipv4_network is not None:
            if st_ipv4_network.in_network(st_ipv4):
                if st_ipv4 > high_ipv4:
                    high_ipv4 = st_ipv4

        if st_ipv6 and st_ipv6_network is not None:
            if st_ipv6_network.in_network(st_ipv6):
                if st_ipv6 > high_ipv6:
                    high_ipv6 = st_ipv6

    if high_ipv4 is None and st_ipv4_network is not None:
        high_ipv4 = sipcalc_type("%s/%d" % (
            st_ipv4_network.usable_range[0],
            st_ipv4_network.network_mask_bits,
        ))

    elif high_ipv4 is not None and st_ipv4_network is not None:
        high_ipv4 += 1
        if not st_ipv4_network.in_network(high_ipv4):
            high_ipv4 = None

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
    bridge_ipv4 = None
    if st_ipv4_network is not None and not st_host_ipv4_network:
        bridge_ipv4 = sipcalc_type("%s/%d" % (
            st_ipv4_network.usable_range[0],
            st_ipv4_network.network_mask_bits,
        ))

    bridge_ipv6 = None
    if st_ipv6_network is not None:
        bridge_ipv6 = sipcalc_type("%s/%d" % (
            st_ipv6_network.network_range[0],
            st_ipv6_network.prefix_length,
        ))

    return {
        'high_ipv4': high_ipv4,
        'high_ipv6': high_ipv6,
        'bridge_ipv4': bridge_ipv4,
        'bridge_ipv6': bridge_ipv6,
    }
