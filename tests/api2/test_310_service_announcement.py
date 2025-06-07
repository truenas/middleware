import contextlib
import random
import re
import socket
import string
from datetime import datetime, timedelta
from time import sleep
from typing import cast

import pytest
from assets.websocket.server import reboot
from assets.websocket.service import (ensure_service_disabled,
                                      ensure_service_enabled,
                                      ensure_service_started,
                                      ensure_service_stopped)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from pytest_dependency import depends
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

from auto_config import ha, password, pool_name, user
from functions import SSH_TEST
from protocols import smb_share

digits = ''.join(random.choices(string.digits, k=4))
dataset_name = f"smb-cifs{digits}"
SMB_NAME1 = f"TestCifsSMB{digits}"
SMB_PATH1 = f"/mnt/{pool_name}/{dataset_name}"

dataset_name2 = f"other{digits}"
SMB_NAME2 = f"OtherTestSMB{digits}"
SMB_PATH2 = f"/mnt/{pool_name}/{dataset_name2}"

# Service names
TIME_MACHINE = '_adisk._tcp.local.'  # Automatic Disk
DEVICE_INFO = '_device-info._tcp.local.'  # Device Info
HTTP = '_http._tcp.local.'
SMB = '_smb._tcp.local.'
NUT = '_nut._tcp'

DO_MDNS_REBOOT_TEST = False
USE_AVAHI_BROWSE = True
skip_avahi_browse_tests = pytest.mark.skipif(USE_AVAHI_BROWSE, reason="Skip tests broken by use of avahi-browse")


def _get_tm_props(rec, key):
    result = {}
    for pair in rec['properties'][key].decode('utf-8').split(','):
        k, v = pair.split('=')
        result[k] = v
    return result


def allow_settle(delay=3):
    # Delay slightly to allow things to propagate
    sleep(delay)


@contextlib.contextmanager
def service_announcement_config(config):
    if not config:
        yield
    else:
        old_config = call('network.configuration.config')['service_announcement']
        call('network.configuration.update', {'service_announcement': config})
        try:
            yield
        finally:
            call('network.configuration.update', {'service_announcement': old_config})


@contextlib.contextmanager
def ensure_aapl_extensions():
    # First check
    enabled = call('smb.config')['aapl_extensions']
    if enabled:
        yield
    else:
        call('smb.update', {'aapl_extensions': True})
        try:
            yield
        finally:
            call('smb.update', {'aapl_extensions': False})


def wait_for_avahi_startup(interval=5, timeout=300):
    """When tests are running in a QE environment it can take a long
    time for the service to start up completely, because many systems
    can be configured with the same hostname.

    This function will detect the most recent avahi-daemon startup and
    wait for it to complete"""
    command = 'journalctl --no-pager -u avahi-daemon --since "10 minute ago"'
    brackets = re.compile(r'[\[\]]+')
    while timeout > 0:
        startup = None
        ssh_out = SSH_TEST(command, user, password)
        assert ssh_out['result'], str(ssh_out)
        output = ssh_out['output']
        # First we just look for the most recent startup command
        for line in output.split('\n'):
            if line.endswith('starting up.'):
                startup = line
        if startup:
            pid = brackets.split(startup)[1]
            completion = f'avahi-daemon[{pid}]: Server startup complete.'
            for line in output.split('\n'):
                if completion in line:
                    # Did we just complete
                    finish_plus_five = (datetime.strptime(line.split()[2], "%H:%M:%S") + timedelta(seconds=5)).time()
                    if finish_plus_five > datetime.now().time():
                        # Wait 5 seconds to ensure services are published
                        sleep(5)
                    return True
        sleep(interval)
        timeout -= interval
    return False


class ZeroconfCollector:

    def on_service_state_change(self, zeroconf, service_type, name, state_change):

        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                item = {}
                item['addresses'] = [addr for addr in info.parsed_scoped_addresses()]
                if self.ip not in item['addresses']:
                    return
                item['port'] = cast(int, info.port)
                item['server'] = info.server
                if info.properties:
                    item['properties'] = {}
                    for key, value in info.properties.items():
                        if key:
                            item['properties'][key] = value
                else:
                    item['properties'] = {}
                self.result[service_type][name] = item
                self.update_internal_hostname(item['server'])

    def find_items(self, service_announcement=None, timeout=5):
        self.result = {}
        for service in self.SERVICES:
            self.result[service] = {}
        with service_announcement_config(service_announcement):
            assert wait_for_avahi_startup(), "Failed to detect avahi-daemon startup"
            zeroconf = Zeroconf()
            ServiceBrowser(zeroconf, self.SERVICES, handlers=[self.on_service_state_change])
            try:
                sleep(timeout)
            finally:
                zeroconf.close()
        return self.result

    def clear_cache(self):
        # No-op for zeroconf collector
        pass


class AvahiBrowserCollector:

    name_to_service = {
        'Device Info': DEVICE_INFO,
        'Web Site': HTTP,
        'Microsoft Windows Network': SMB,
        'Apple TimeMachine': TIME_MACHINE,
        '_nut._tcp': NUT,
    }

    def find_items(self, service_announcement=None, timeout=5):
        self.result = {}
        for service in self.SERVICES:
            self.result[service] = {}
        with service_announcement_config(service_announcement):
            assert wait_for_avahi_startup(), "Failed to detect avahi-daemon startup"
            # ssh_out = SSH_TEST("avahi-browse -v --all -t -p --resolve", user, password)
            # Appears sometimes we need a little more time
            ssh_out = SSH_TEST("timeout --preserve-status 5 avahi-browse -v --all -p --resolve", user, password)
            assert ssh_out['result'], str(ssh_out)
            output = ssh_out['output']
            for line in output.split('\n'):
                item = {}
                items = line.split(';')
                if len(items) > 1 and items[0] == '=':
                    if len(items) == 10:
                        server = items[3]
                        pub_ip = items[7]
                        if pub_ip not in self.ips:
                            continue
                        item['addresses'] = [pub_ip]
                        item['port'] = items[8]
                        item['server'] = items[6]
                        service_type = AvahiBrowserCollector.name_to_service[items[4]]
                        key = f"{server}.{service_type}"
                        item['properties'] = self.process_properties(items[9], service_type)
                        self.result[service_type][key] = item
                        self.update_internal_hostname(item['server'])
        return self.result

    def process_properties(self, txts, service_type):
        props = {}
        for txt in txts.split():
            if txt.startswith('"') and txt.endswith('"'):
                txt = txt[1:-1]
                for prop in ['model', 'dk0', 'dk1', 'sys']:
                    if txt.startswith(f"{prop}="):
                        props[prop.encode('utf-8')] = txt[len(prop) + 1:].encode('utf-8')
        return props

    def clear_cache(self):
        # We need to restart the avahi-daemon to clear cache
        # print("Clearing cache")
        ssh("systemctl restart avahi-daemon")

    @staticmethod
    def get_ipv6(ip):
        """Given an IPv4 address string, find the IPv6 on the same
        interface (if present).  Returns either the IPv6 address as
        a string, or None"""
        ips = call('network.general.summary')['ips']
        for interface in ips:
            matched = False
            if 'IPV4' in ips[interface]:
                for ipv4 in ips[interface]['IPV4']:
                    if ipv4.split('/')[0] == ip:
                        matched = True
                        break
            if matched and 'IPV6' in ips[interface]:
                for ipv6 in ips[interface]['IPV6']:
                    return ipv6.split('/')[0]
        return None


class abstractmDNSAnnounceCollector:
    """
    Class to help in the discovery (and processing/checking)
    of services advertised by a particular IP address/server name.
    """
    SERVICES = [TIME_MACHINE, DEVICE_INFO, HTTP, SMB, NUT]

    def __init__(self, ip, tn_hostname):
        self.ip = socket.gethostbyname(ip)
        self.hostname = self.tn_hostname = tn_hostname

    def update_internal_hostname(self, published_hostname):
        """If there has been a conflict then it is possible that a derivative
        of the original hostname is being used.  Check whether this the
        published name could be a conflict-resolved name and if so,
        update the hostname that will be used during checks.
        """
        if published_hostname == self.tn_hostname:
            return
        possible_new_hostname = published_hostname.split('.')[0]
        if possible_new_hostname == self.hostname:
            return
        # Check whether either 'hostname-...' or '<hostname> #...'
        if possible_new_hostname.split()[0].split('-')[0] == self.tn_hostname:
            self.hostname = possible_new_hostname

    def has_service_type(self, hostname, service_type):
        if not hostname:
            hostname = self.hostname
        key = f"{hostname}.{service_type}"
        return key in self.result[service_type]

    def get_service_type(self, hostname, service_type):
        if not hostname:
            hostname = self.hostname
        key = f"{hostname}.{service_type}"
        if key in self.result[service_type]:
            return self.result[service_type][key]

    def has_time_machine(self, hostname=None):
        return self.has_service_type(hostname, TIME_MACHINE)

    def has_device_info(self, hostname=None):
        return self.has_service_type(hostname, DEVICE_INFO)

    def has_http(self, hostname=None):
        return self.has_service_type(hostname, HTTP)

    def has_smb(self, hostname=None):
        return self.has_service_type(hostname, SMB)

    def time_machine(self, hostname=None):
        return self.get_service_type(hostname, TIME_MACHINE)

    def check_present(self, device_info=True, http=True, smb=True, time_machine=True, hostname=None):
        assert self.has_device_info(hostname) == device_info, self.result[DEVICE_INFO]
        assert self.has_http(hostname) == http, self.result[HTTP]
        assert self.has_smb(hostname) == smb, self.result[SMB]
        assert self.has_time_machine(hostname) == time_machine, self.result[TIME_MACHINE]


if USE_AVAHI_BROWSE:
    class mDNSAnnounceCollector(abstractmDNSAnnounceCollector, AvahiBrowserCollector):
        def __init__(self, ip, tn_hostname):
            abstractmDNSAnnounceCollector.__init__(self, ip, tn_hostname)
            # avahi-browse can report either an IPv4 address or the
            # corresponding IPv6 address if configured on the same interface
            # So we will expand our inclusion check to encompass both.
            ipv6 = AvahiBrowserCollector.get_ipv6(self.ip)
            if ipv6:
                self.ips = [self.ip, ipv6]
            else:
                self.ips = [self.ip]
else:
    class mDNSAnnounceCollector(abstractmDNSAnnounceCollector, ZeroconfCollector):
        pass


@pytest.fixture(autouse=True, scope="module")
def setup_environment():
    try:
        with ensure_service_disabled('cifs'):
            with ensure_service_stopped('cifs'):
                yield
    finally:
        pass


@pytest.mark.timeout(600)
@pytest.mark.dependency(name="servann_001")
def test_001_initial_config(request):
    """Ensure that the service announcement configuration is as expected."""
    global current_hostname

    network_config = call('network.configuration.config')
    sa = network_config['service_announcement']
    if ha:
        current_hostname = network_config['hostname_virtual']
    else:
        current_hostname = network_config['hostname']
    # At the moment we only care about mdns
    assert sa['mdns'] is True, sa

    # Let's restart avahi (in case we've updated middleware)
    call('service.control', 'RESTART', 'mdns', job=True)
    ac = mDNSAnnounceCollector(truenas_server.ip, current_hostname)
    ac.find_items()
    ac.check_present(smb=False, time_machine=False)


# This test is broken by the use of avahi-browse as when it is
# called it re-activates the avahi-daemon by means of the
# avahi-daemon.socket.
# The DEV and HTTP service files have NOT been deleted upon
# a service stop, so this reactivation causes the test to
# fail.
# Since the test passes when run with zeroconf library on
# a suitably connected test-runner, no real need to chase.
@pytest.mark.timeout(600)
@skip_avahi_browse_tests
def test_002_mdns_disabled(request):
    depends(request, ["servann_001"], scope="session")
    ac = mDNSAnnounceCollector(truenas_server.ip, current_hostname)
    ac.clear_cache()
    ac.find_items({'mdns': False, 'wsd': True, 'netbios': False})
    ac.check_present(False, False, False, False)


# Setting a VERY long timeout as when this test is run in isolation
# on jenkins there can be many (20+) hostname clashes which means
# avahi can take a LONG time to settle down/start up.
#
# We could avoid by setting a unique hostname (as is done during a
# full test run), but it also seems worthwhile exercise to be able
# to test in such a unsuitable environment.
@pytest.mark.timeout(900)
def test_003_mdns_smb_share(request):
    """Perform some mDNS tests wrt SMB and ADISK services."""
    depends(request, ["servann_001"], scope="session")

    # SMB is not started originally
    ac = mDNSAnnounceCollector(truenas_server.ip, current_hostname)
    ac.find_items()
    ac.check_present(smb=False, time_machine=False)

    with dataset(dataset_name):
        with smb_share(SMB_PATH1, {'name': SMB_NAME1, 'comment': 'Test SMB Share'}):
            # SMB is still not started
            ac.find_items()
            ac.check_present(smb=False, time_machine=False)
            with ensure_service_started('cifs'):
                allow_settle()
                ac.find_items()
                ac.check_present(time_machine=False)
            # OK, the SMB is stopped again,  Ensure we don't advertise SMB anymore
            ac.clear_cache()
            ac.find_items()
            ac.check_present(smb=False, time_machine=False)

        # Now we're going to setup a time machine share
        with ensure_aapl_extensions():
            with ensure_service_started('cifs'):
                allow_settle()
                # Check mDNS before we have a time machine share
                ac.find_items()
                ac.check_present(time_machine=False)
                with smb_share(SMB_PATH1, {'name': SMB_NAME1,
                                           'comment': 'Basic TM SMB Share',
                                           'purpose': 'TIMEMACHINE_SHARE'}) as shareID1:
                    allow_settle()
                    # Check mDNS now we have a time machine share
                    ac.find_items()
                    ac.check_present()

                    # Now read the share details and then check against what mDNS reported
                    share1 = call('sharing.smb.query', [['id', '=', shareID1]])[0]

                    tm = ac.time_machine()
                    props = _get_tm_props(tm, b'dk0')
                    assert props['adVN'] == SMB_NAME1, props
                    assert props['adVF'] == '0x82', props
                    assert props['adVU'] == share1['vuid'], props
                    # Now make another time machine share
                    with dataset(dataset_name2):
                        with smb_share(SMB_PATH2, {'name': SMB_NAME2,
                                                   'comment': 'Multiuser TM SMB Share',
                                                   'purpose': 'TIMEMACHINE_SHARE'}) as shareID2:
                            share2 = call('sharing.smb.query', [['id', '=', shareID2]])[0]
                            allow_settle()
                            ac.find_items()
                            ac.check_present()
                            tm = ac.time_machine()
                            props0 = _get_tm_props(tm, b'dk0')
                            props1 = _get_tm_props(tm, b'dk1')
                            assert props0['adVF'] == '0x82', props0
                            assert props1['adVF'] == '0x82', props1
                            # Let's not make any assumption about which share is which
                            if props0['adVN'] == SMB_NAME1:
                                # SHARE 1 in props0
                                assert props0['adVU'] == share1['vuid'], props0
                                # SHARE 2 in props1
                                assert props1['adVN'] == SMB_NAME2, props1
                                assert props1['adVU'] == share2['vuid'], props1
                            else:
                                # SHARE 1 in props1
                                assert props1['adVN'] == SMB_NAME1, props1
                                assert props1['adVU'] == share1['vuid'], props1
                                # SHARE 2 in props0
                                assert props0['adVN'] == SMB_NAME2, props0
                                assert props0['adVU'] == share2['vuid'], props0
                    # Still have one TM share
                    allow_settle()
                    ac.find_items()
                    ac.check_present()

                # Check mDNS now we no longer have a time machine share
                ac.clear_cache()
                ac.find_items()
                ac.check_present(time_machine=False)
            # Finally check when SMB is stopped again
            ac.clear_cache()
            ac.find_items()
            ac.check_present(smb=False, time_machine=False)


if DO_MDNS_REBOOT_TEST:
    def test_004_reboot_with_mdns_smb_share(request):
        """Create a time-machine SMB and check that it is published
        following a reboot."""
        depends(request, ["servann_001"], scope="session")

        # First let's setup a time machine share
        with dataset(dataset_name):
            with smb_share(SMB_PATH1, {'name': SMB_NAME1,
                                       'comment': 'Basic TM SMB Share',
                                       'purpose': 'TIMEMACHINE'}):
                with ensure_service_enabled('cifs'):
                    # Next reboot and then check the expected services
                    # are advertised.
                    reboot(truenas_server.ip, 'cifs')
                    ac = mDNSAnnounceCollector(truenas_server.ip, current_hostname)
                    ac.find_items()
                    ac.check_present()
