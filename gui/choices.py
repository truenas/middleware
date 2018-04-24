# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import freenasUI.settings
import csv
import logging
import os
import re
import sqlite3
import copy
import subprocess
import codecs

from os import popen
from django.utils.translation import ugettext_lazy as _

from freenasUI.middleware.client import client

log = logging.getLogger('choices')

HTAUTH_CHOICES = (
    ('none', _('No Authentication')),
    ('basic', _('Basic Authentication')),
    ('digest', _('Digest Authentication')),
)

SMTPAUTH_CHOICES = (
    ('plain', _('Plain')),
    ('ssl', _('SSL')),
    ('tls', _('TLS')),
)

# GUI protocol choice
PROTOCOL_CHOICES = (
    ('http', _('HTTP')),
    ('https', _('HTTPS')),
    ('httphttps', _('HTTP+HTTPS')),
)

TRANSFERMODE_CHOICES = (
    ('Auto', _('Auto')),
    ('PIO0', _('PIO0')),
    ('PIO1', _('PIO1')),
    ('PIO2', _('PIO2')),
    ('PIO3', _('PIO3')),
    ('PIO4', _('PIO4')),
    ('WDMA0', _('WDMA0')),
    ('WDMA1', _('WDMA1')),
    ('WDMA2', _('WDMA2')),
    ('UDMA16', _('UDMA-16')),
    ('UDMA33', _('UDMA-33')),
    ('UDMA66', _('UDMA-66')),
    ('UDMA100', _('UDMA-100')),
    ('UDMA133', _('UDMA-133')),
    ('SATA150', _('SATA 1.5Gbit/s')),
    ('SATA300', _('SATA 3.0Gbit/s')),
)

HDDSTANDBY_CHOICES = (
    ('Always On', _('Always On')),
    ('5', '5'),
    ('10', '10'),
    ('20', '20'),
    ('30', '30'),
    ('60', '60'),
    ('120', '120'),
    ('180', '180'),
    ('240', '240'),
    ('300', '300'),
    ('330', '330'),
)

ADVPOWERMGMT_CHOICES = (
    ('Disabled', _('Disabled')),
    ('1', _('Level 1 - Minimum power usage with Standby (spindown)')),
    ('64', _('Level 64 - Intermediate power usage with Standby')),
    ('127', _('Level 127 - Maximum power usage with Standby')),
    ('128', _('Level 128 - Minimum power usage without Standby (no spindown)')),
    ('192', _('Level 192 - Intermediate power usage without Standby')),
    ('254', _('Level 254 - Maximum performance, maximum power usage')),
)

ACOUSTICLVL_CHOICES = (
    ('Disabled', _('Disabled')),
    ('Minimum', _('Minimum')),
    ('Medium', _('Medium')),
    ('Maximum', _('Maximum')),
)

MINUTES1_CHOICES = tuple([(str(x), str(x)) for x in range(0, 12)])

MINUTES2_CHOICES = tuple([(str(x), str(x)) for x in range(12, 24)])

MINUTES3_CHOICES = tuple([(str(x), str(x)) for x in range(24, 36)])

MINUTES4_CHOICES = tuple([(str(x), str(x)) for x in range(36, 48)])

MINUTES5_CHOICES = tuple([(str(x), str(x)) for x in range(48, 60)])

HOURS1_CHOICES = tuple([(str(x), str(x)) for x in range(0, 12)])

HOURS2_CHOICES = tuple([(str(x), str(x)) for x in range(12, 24)])

DAYS1_CHOICES = tuple([(str(x), str(x)) for x in range(1, 13)])

DAYS2_CHOICES = tuple([(str(x), str(x)) for x in range(13, 25)])

DAYS3_CHOICES = tuple([(str(x), str(x)) for x in range(25, 32)])


MONTHS_CHOICES = (
    ('1', _('January')),
    ('2', _('February')),
    ('3', _('March')),
    ('4', _('April')),
    ('5', _('May')),
    ('6', _('June')),
    ('7', _('July')),
    ('8', _('August')),
    ('9', _('September')),
    ('10', _('October')),
    ('11', _('November')),
    ('12', _('December')),
)

WEEKDAYS_CHOICES = (
    ('1', _('Monday')),
    ('2', _('Tuesday')),
    ('3', _('Wednesday')),
    ('4', _('Thursday')),
    ('5', _('Friday')),
    ('6', _('Saturday')),
    ('7', _('Sunday')),
)

VolumeEncrypt_Choices = (
    (0, _('Unencrypted')),
    (1, _('Encrypted, no passphrase')),
    (2, _('Encrypted, with passphrase')),
)

CIFS_SMB_PROTO_CHOICES = (
    ('CORE', _('CORE')),
    ('COREPLUS', _('COREPLUS')),
    ('LANMAN1', _('LANMAN1')),
    ('LANMAN2', _('LANMAN2')),
    ('NT1', _('NT1')),
    ('SMB2', _('SMB2')),
    ('SMB2_02', _('SMB2_02')),
    ('SMB2_10', _('SMB2_10')),
    ('SMB3', _('SMB3')),
    ('SMB3_00', _('SMB3_00')),
    ('SMB3_02', _('SMB3_02')),
    ('SMB3_11', _('SMB3_11')),
)

DOSCHARSET_CHOICES = (
    'CP437',
    'CP850',
    'CP852',
    'CP866',
    'CP932',
    'CP949',
    'CP950',
    'CP1026',
    'CP1251',
    'ASCII',
)

UNIXCHARSET_CHOICES = (
    'UTF-8',
    'ISO-8859-1',
    'ISO-8859-15',
    'GB2312',
    'EUC-JP',
    'ASCII',
)


class CHARSET(object):

    __CODEPAGE = re.compile("(?P<name>CP|GB|ISO-8859-|UTF-)(?P<num>\d+)").match

    __canonical = {'UTF-8', 'ASCII', 'GB2312', 'HZ-GB-2312', 'CP1361'}

    def __check_codec(self, encoding):
        try:
            if codecs.lookup(encoding):
                return encoding.upper()
        except LookupError:
            pass
        return

    def __key_cp(self, encoding):
        cp = CHARSET.__CODEPAGE(encoding)
        if cp:
            return tuple((cp.group('name'), int(cp.group('num'), 10)))
        return tuple((encoding, float('inf')))

    def __init__(self, popular=[]):

        self.__popular = popular

        out = subprocess.Popen(['/usr/bin/iconv', '-l'], stdout=subprocess.PIPE, encoding='utf8').communicate()[0]

        encodings = set()
        for line in out.splitlines():
            enc = [e for e in line.split() if self.__check_codec(e)]
            if enc:
                cp = enc[0]
                for e in enc:
                    if e in CHARSET.__canonical:
                        cp = e
                        break
                encodings.add(cp)

        self.__charsets = [c for c in sorted(encodings, key=self.__key_cp) if c not in self.__popular]

    def __iter__(self):
        if self.__popular:
            for c in self.__popular:
                yield(c, c)
            yield('', '-----')

        for c in self.__charsets:
            yield(c, c)


LOGLEVEL_CHOICES = (
    ('0', _('None')),
    ('1', _('Minimum')),
    ('2', _('Normal')),
    ('3', _('Full')),
    ('10', _('Debug')),
)

CASEFOLDING_CHOICES = (
    ('none', _('No case folding')),
    ('lowercaseboth', _('Lowercase names in both directions')),
    ('uppercaseboth', _('Lowercase names in both directions')),
    ('lowercaseclient', _('Client sees lowercase, server sees uppercase')),
    ('uppercaseclient', _('Client sees uppercase, server sees lowercase')),
)

TARGET_BLOCKSIZE_CHOICES = (
    (512, '512'),
    (1024, '1024'),
    (2048, '2048'),
    (4096, '4096'),
)

EXTENT_RPM_CHOICES = (
    ('Unknown', _('Unknown')),
    ('SSD', _('SSD')),
    ('5400', _('5400')),
    ('7200', _('7200')),
    ('10000', _('10000')),
    ('15000', _('15000')),
)

AUTHMETHOD_CHOICES = (
    ('None', _('None')),
    ('CHAP', _('CHAP')),
    ('CHAP Mutual', _('Mutual CHAP')),
)

AUTHGROUP_CHOICES = (
    ('None', _('None')),
)

DYNDNSPROVIDER_CHOICES = (
    ('dyndns@3322.org', '3322.org'),
    ('default@changeip.com', 'changeip.com'),
    ('default@cloudxns.net', 'cloudxns.net'),
    ('default@ddnss.de', 'ddnss.de'),
    ('default@dhis.org', 'dhis.org'),
    ('default@dnsexit.com', 'dnsexit.com'),
    ('default@dnsomatic.com', 'dnsomatic.com'),
    ('default@dnspod.cn', 'dnspod.cn'),
    ('default@domains.google.com', 'domains.google.com'),
    ('default@dtdns.com', 'dtdns.com'),
    ('default@duckdns.org', 'duckdns.org'),
    ('default@duiadns.net', 'duiadns.net'),
    ('default@dyndns.org', 'dyndns.org'),
    ('default@dynsip.org', 'dynsip.org'),
    ('default@dynv6.com', 'dynv6.com'),
    ('default@easydns.com', 'easydns.com'),
    ('default@freedns.afraid.org', 'freedns.afraid.org'),
    ('default@freemyip.com', 'freemyip.com'),
    ('default@gira.de', 'gira.de'),
    ('ipv6tb@he.net', 'he.net'),
    ('default@ipv4.dynv6.com', 'ipv4.dynv6.com'),
    ('default@loopia.com', 'loopia.com'),
    ('default@no-ip.com', 'no-ip.com'),
    ('ipv4@nsupdate.info', 'nsupdate.info'),
    ('default@ovh.com', 'ovh.com'),
    ('default@sitelutions.com', 'sitelutions.com'),
    ('default@spdyn.de', 'spdyn.de'),
    ('default@strato.com', 'strato.com'),
    ('default@tunnelbroker.net', 'tunnelbroker.net'),
    ('default@tzo.com', 'tzo.com'),
    ('default@zerigo.com', 'zerigo.com'),
    ('default@zoneedit.com', 'zoneedit.com'),
    ('custom', 'Custom Provider')
)

SNMP_CHOICES = (
    ('mibll', 'Mibll'),
    ('netgraph', 'Netgraph'),
    ('hostresources', 'Host resources'),
    ('UCD-SNMP-MIB ', 'UCD-SNMP-MIB'),
)

SNMP_LOGLEVEL = (
    (0, _('Emergency')),
    (1, _('Alert')),
    (2, _('Critical')),
    (3, _('Error')),
    (4, _('Warning')),
    (5, _('Notice')),
    (6, _('Info')),
    (7, _('Debug')),
)

UPS_CHOICES = (
    ('lowbatt', _('UPS reaches low battery')),
    ('batt', _('UPS goes on battery')),
)

BTENCRYPT_CHOICES = (
    ('preferred', _('Preferred')),
    ('tolerated', _('Tolerated')),
    ('required', _('Required')),
)

PWEncryptionChoices = (
    ('clear', 'clear'),
    ('crypt', 'crypt'),
    ('md5', 'md5'),
    ('nds', 'nds'),
    ('racf', 'racf'),
    ('ad', 'ad'),
    ('exop', 'exop'),
)

LAGGType = (
    ('failover', 'Failover'),
    ('lacp', 'LACP'),
    ('loadbalance', 'Load Balance'),
    ('roundrobin', 'Round Robin'),
    ('none', 'None'),
)

VLAN_PCP_CHOICES = (
    (0, _('Best effort (default)')),
    (1, _('Background (lowest)')),
    (2, _('Excellent effort')),
    (3, _('Critical applications')),
    (4, _('Video, < 100ms latency')),
    (5, _('Video, < 10ms latency')),
    (6, _('Internetwork control')),
    (7, _('Network control (highest)')),
)

ZFS_AtimeChoices = (
    ('inherit', _('Inherit')),
    ('on', _('On')),
    ('off', _('Off')),
)

ZFS_ReadonlyChoices = (
    ('inherit', _('Inherit')),
    ('on', _('On')),
    ('off', _('Off')),
)


ZFS_ExecChoices = (
    ('inherit', _('Inherit')),
    ('on', _('On')),
    ('off', _('Off')),
)

ZFS_SyncChoices = (
    ('inherit', _('Inherit')),
    ('standard', _('Standard')),
    ('always', _('Always')),
    ('disabled', _('Disabled')),
)

ZFS_CompressionChoices = (
    ('inherit', _('Inherit')),
    ('off', _('Off')),
    ('lz4', _('lz4 (recommended)')),
    ('gzip', _('gzip (default level, 6)')),
    ('gzip-1', _('gzip (fastest)')),
    ('gzip-9', _('gzip (maximum, slow)')),
    ('zle', _('zle (runs of zeros)')),
    ('lzjb', _('lzjb (legacy, not recommended)')),
)

Repl_CompressionChoices = (
    ('off', _('Off')),
    ('lz4', _('lz4 (fastest)')),
    ('pigz', _('pigz (all rounder)')),
    ('plzip', _('plzip (best compression)')),
)


class whoChoices:
    """Populate a list of system user choices"""
    def __init__(self):
        # This doesn't work right, lol
        pipe = popen("pw usershow -a | cut -d: -f1")
        self._wholist = pipe.read().strip().split('\n')
        self.max_choices = len(self._wholist)

    def __iter__(self):
        return iter((i, i) for i in self._wholist)


# Network|Interface Management
class NICChoices(object):
    """Populate a list of NIC choices"""
    def __init__(self, nolagg=False, novlan=False, noloopback=True, notap=True,
                 exclude_configured=True, include_vlan_parent=False,
                 exclude_unconfigured_vlan_parent=False,
                 with_alias=False, nobridge=True, noepair=True, include_lagg_parent=True):

        self.nolagg = nolagg
        self.novlan = novlan
        self.noloopback = noloopback
        self.notap = notap
        self.exclude_configured = exclude_configured
        self.include_vlan_parent = include_vlan_parent
        self.exclude_unconfigured_vlan_parent = exclude_unconfigured_vlan_parent
        self.with_alias = with_alias
        self.nobridge = nobridge
        self.noepair = noepair
        self.include_lagg_parent = include_lagg_parent

    def __iter__(self):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        self._NIClist = [y for y in self._NIClist if y not in ('lo0', 'pfsync0', 'pflog0', 'ipfw0')]
        if self.noloopback is False:
            self._NIClist.append('lo0')

        from freenasUI.middleware.notifier import notifier
        # Remove internal interfaces for failover
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_licensed()
        ):
            for iface in notifier().failover_internal_interfaces():
                if iface in self._NIClist:
                    self._NIClist.remove(iface)

        conn = sqlite3.connect(freenasUI.settings.DATABASES['default']['NAME'])
        c = conn.cursor()
        # Remove interfaces that are parent devices of a lagg
        # Database queries are wrapped in try/except as this is run
        # before the database is created during syncdb and the queries
        # will fail
        if self.include_lagg_parent:
            try:
                c.execute("SELECT lagg_physnic FROM network_lagginterfacemembers")
            except sqlite3.OperationalError:
                pass
            else:
                for interface in c:
                    if interface[0] in self._NIClist:
                        self._NIClist.remove(interface[0])

        if self.nolagg:
            # vlan devices are not valid parents of laggs
            self._NIClist = [nic for nic in self._NIClist if not nic.startswith("lagg")]
            self._NIClist = [nic for nic in self._NIClist if not nic.startswith("vlan")]
        if self.novlan:
            self._NIClist = [nic for nic in self._NIClist if not nic.startswith("vlan")]
        else:
            # This removes devices that are parents of vlans.  We don't
            # remove these devices if we are adding a vlan since multiple
            # vlan devices may share the same parent.
            # The exception to this case is when we are getting the NIC
            # list for the GUI, in which case we want the vlan parents
            # as they may have a valid config on them.
            if not self.include_vlan_parent or self.exclude_unconfigured_vlan_parent:
                try:
                    c.execute("SELECT vlan_pint FROM network_vlan")
                except sqlite3.OperationalError:
                    pass
                else:
                    for interface in c:
                        if interface[0] in self._NIClist:
                            self._NIClist.remove(interface[0])

            if self.exclude_unconfigured_vlan_parent:
                # Add the configured VLAN parents back in
                try:
                    c.execute("SELECT vlan_pint FROM network_vlan "
                              "INNER JOIN network_interfaces ON "
                              "network_vlan.vlan_pint=network_interfaces.int_interface "
                              "WHERE network_interfaces.int_interface IS NOT NULL "
                              "AND ((network_interfaces.int_ipv4address != '' "
                              "AND network_interfaces.int_ipv4address IS NOT NULL) "
                              "OR network_interfaces.int_dhcp = 1)")
                except sqlite3.OperationalError:
                    pass
                else:
                    for interface in c:
                        if interface[0] not in self._NIClist:
                            self._NIClist.append(interface[0])

        if self.with_alias:
            try:
                sql = """
                    SELECT
                        int_interface

                    FROM
                        network_interfaces as ni

                    INNER JOIN
                        network_alias as na
                    ON
                        na.alias_interface_id = ni.id
                """
                c.execute(sql)

            except sqlite3.OperationalError:
                pass

            else:
                aliased_nics = [x[0] for x in c]
                niclist = copy.deepcopy(self._NIClist)
                for interface in niclist:
                    if interface not in aliased_nics:
                        self._NIClist.remove(interface)

        if self.exclude_configured:
            try:
                # Exclude any configured interfaces
                c.execute("SELECT int_interface FROM network_interfaces")
            except sqlite3.OperationalError:
                pass
            else:
                for interface in c:
                    if interface[0] in self._NIClist:
                        self._NIClist.remove(interface[0])

        if self.nobridge:
            self._NIClist = [nic for nic in self._NIClist if not nic.startswith("bridge")]

        if self.noepair:
            niclist = copy.deepcopy(self._NIClist)
            for nic in niclist:
                if nic.startswith('epair'):
                    self._NIClist.remove(nic)

        if self.notap:
            taplist = copy.deepcopy(self._NIClist)
            for nic in taplist:
                if nic.startswith('tap'):
                    self._NIClist.remove(nic)

        self.max_choices = len(self._NIClist)

        return iter((i, i) for i in self._NIClist)


class IPChoices(NICChoices):

    def __init__(
        self,
        ipv4=True,
        ipv6=True,
        nolagg=False,
        novlan=False,
        noloopback=True,
        exclude_configured=False,
        include_vlan_parent=True
    ):
        super(IPChoices, self).__init__(
            nolagg=nolagg,
            novlan=novlan,
            noloopback=noloopback,
            exclude_configured=exclude_configured,
            include_vlan_parent=include_vlan_parent
        )
        self.ipv4 = ipv4
        self.ipv6 = ipv6

    def __iter__(self):
        self._NIClist = list(super(IPChoices, self).__iter__())

        from freenasUI.middleware.notifier import notifier
        _n = notifier()
        carp = False
        if not _n.is_freenas():
            try:
                if _n.failover_status() not in ('SINGLE', 'ERROR'):
                    carp = True
            except sqlite3.OperationalError:
                pass

        self._IPlist = []
        for iface in self._NIClist:
            pipe = popen("/sbin/ifconfig %s" % iface[0])
            lines = pipe.read().strip().split('\n')
            for line in lines:
                if carp:
                    reg = re.search(r' vhid (\d+)', line)
                    if not reg:
                        continue
                if line.startswith('\tinet6'):
                    if self.ipv6 is True:
                        self._IPlist.append(line.split(' ')[1].split('%')[0])
                elif line.startswith('\tinet'):
                    if self.ipv4 is True:
                        self._IPlist.append(line.split(' ')[1])
            pipe.close()
            self._IPlist.sort()

        if not self._IPlist:
            return iter([('0.0.0.0', '0.0.0.0')])
        return iter((i, i) for i in self._IPlist)


class TimeZoneChoices:
    """Populate timezone from /usr/share/zoneinfo choices"""
    def __init__(self):
        pipe = popen('find /usr/share/zoneinfo/ -type f -not -name '
                     'zone.tab -not -regex \'.*/Etc/GMT.*\'')
        self._TimeZoneList = pipe.read().strip().split('\n')
        self._TimeZoneList = [x[20:] for x in self._TimeZoneList]
        self._TimeZoneList.sort()
        self.max_choices = len(self._TimeZoneList)

    def __iter__(self):
        return iter((i, i) for i in self._TimeZoneList)


v4NetmaskBitList = (
    ('32', '/32 (255.255.255.255)'),
    ('31', '/31 (255.255.255.254)'),
    ('30', '/30 (255.255.255.252)'),
    ('29', '/29 (255.255.255.248)'),
    ('28', '/28 (255.255.255.240)'),
    ('27', '/27 (255.255.255.224)'),
    ('26', '/26 (255.255.255.192)'),
    ('25', '/25 (255.255.255.128)'),
    ('24', '/24 (255.255.255.0)'),
    ('23', '/23 (255.255.254.0)'),
    ('22', '/22 (255.255.252.0)'),
    ('21', '/21 (255.255.248.0)'),
    ('20', '/20 (255.255.240.0)'),
    ('19', '/19 (255.255.224.0)'),
    ('18', '/18 (255.255.192.0)'),
    ('17', '/17 (255.255.128.0)'),
    ('16', '/16 (255.255.0.0)'),
    ('15', '/15 (255.254.0.0)'),
    ('14', '/14 (255.252.0.0)'),
    ('13', '/13 (255.248.0.0)'),
    ('12', '/12 (255.240.0.0)'),
    ('11', '/11 (255.224.0.0)'),
    ('10', '/10 (255.192.0.0)'),
    ('9', '/9 (255.128.0.0)'),
    ('8', '/8 (255.0.0.0)'),
    ('7', '/7 (254.0.0.0)'),
    ('6', '/6 (252.0.0.0)'),
    ('5', '/5 (248.0.0.0)'),
    ('4', '/4 (240.0.0.0)'),
    ('3', '/3 (224.0.0.0)'),
    ('2', '/2 (192.0.0.0)'),
    ('1', '/1 (128.0.0.0)'),
)

v6NetmaskBitList = tuple([(str(i), '/' + str(i)) for i in range(0, 132, 4)])

RetentionUnit_Choices = (
    ('hour', _('Hour(s)')),
    ('day', _('Day(s)')),
    ('week', _('Week(s)')),
    ('month', _('Month(s)')),
    ('year', _('Year(s)')),
)

RepeatUnit_Choices = (
    ('daily', _('Everyday')),
    ('weekly', _('Every selected weekday')),
    # ('monthly', _('Every these days of month')),
    # ('yearly', _('Every these days of specified months')),
)

ACCESS_MODE = (
    ('ro', _('Read-only')),
    ('wo', _('Write-only')),
    ('rw', _('Read and Write')),
)

ZFS_DEDUP = (
    ('on', _('On')),
    ('verify', _('Verify')),
    ('off', _('Off')),
)

ZFS_DEDUP_INHERIT = (
    ('inherit', _('Inherit')),
) + ZFS_DEDUP

TASK_INTERVAL = (
    (5, _("%(minutes)s minutes") % {'minutes': '5'}),
    (10, _("%(minutes)s minutes") % {'minutes': '10'}),
    (15, _("%(minutes)s minutes") % {'minutes': '15'}),
    (30, _("%(minutes)s minutes") % {'minutes': '30'}),
    (60, _("%(hour)s hour") % {'hour': '1'}),
    (120, _("%(hours)s hours") % {'hours': '2'}),
    (180, _("%(hours)s hours") % {'hours': '3'}),
    (240, _("%(hours)s hours") % {'hours': '4'}),
    (360, _("%(hours)s hours") % {'hours': '6'}),
    (720, _("%(hours)s hours") % {'hours': '12'}),
    (1440, _("%(day)s day") % {'day': '1'}),
    (10080, _("%(week)s week") % {'week': '1'}),
    (20160, _("%(weeks)s weeks") % {'weeks': '2'}),
    (40320, _("%(weeks)s weeks") % {'weeks': '4'}),
)

SMART_POWERMODE = (
    ('never', _("Never - Check the device regardless of its power mode")),
    ('sleep', _("Sleep - Check the device unless it is in SLEEP mode")),
    ('standby', _("Standby - Check the device unless it is in SLEEP or STANDBY"
                  " mode")),
    ('idle', _("Idle - Check the device unless it is in SLEEP, STANDBY or IDLE"
               " mode")),
)

SMART_TEST = (
    ('L', _('Long Self-Test')),
    ('S', _('Short Self-Test')),
    ('C', _('Conveyance Self-Test (ATA  only)')),
    ('O', _('Offline Immediate Test (ATA only)')),
)

SERIAL_SPEED = (
    ('9600', _('9600')),
    ('19200', _('19200')),
    ('38400', _('38400')),
    ('57600', _('57600')),
    ('115200', _('115200')),
)

SED_USER = (
    ('user', _('User')),
    ('master', _('Master')),
)


class UPSDRIVER_CHOICES(object):

    def __iter__(self):
        try:
            with client as c:
                driver_choices_dict = c.call('ups.driver_choices')
                for key, value in driver_choices_dict.items():
                    yield (key, value)
        except Exception:
            yield (None, None)


class UPS_PORT_CHOICES(object):

    def __iter__(self):
        try:
            with client as c:
                port_choices = c.call('ups.port_choices')
                for port in port_choices:
                    yield (port, port)
        except Exception:
            yield (None, None)


LDAP_SSL_CHOICES = (
    ('off', _('Off')),
    ('on', _('SSL')),
    ('start_tls', _('TLS')),
)

RSYNC_MODE_CHOICES = (
    ('module', _('Rsync module')),
    ('ssh', _('Rsync over SSH')),
)

RSYNC_DIRECTION = (
    ('push', _('Push')),
    ('pull', _('Pull')),
)


class KBDMAP_CHOICES(object):
    """Populate choices from /usr/share/vt/keymaps/INDEX.keymaps"""
    INDEX = "/usr/share/vt/keymaps/INDEX.keymaps"

    def __iter__(self):
        if not os.path.exists(self.INDEX):
            return
        with open(self.INDEX, 'rb') as f:
            d = f.read().decode('utf8', 'ignore')
        _all = re.findall(r'^(?P<name>[^#\s]+?)\.kbd:en:(?P<desc>.+)$', d, re.M)
        for name, desc in _all:
            yield name, desc


SFTP_LOG_LEVEL = (
    ('QUIET', _('Quiet')),
    ('FATAL', _('Fatal')),
    ('ERROR', _('Error')),
    ('INFO', _('Info')),
    ('VERBOSE', _('Verbose')),
    ('DEBUG', _('Debug')),
    ('DEBUG2', _('Debug2')),
    ('DEBUG3', _('Debug3')),
)


SFTP_LOG_FACILITY = (
    ('DAEMON', _('Daemon')),
    ('USER', _('User')),
    ('AUTH', _('Auth')),
    ('LOCAL0', _('Local 0')),
    ('LOCAL1', _('Local 1')),
    ('LOCAL2', _('Local 2')),
    ('LOCAL3', _('Local 3')),
    ('LOCAL4', _('Local 4')),
    ('LOCAL5', _('Local 5')),
    ('LOCAL6', _('Local 6')),
    ('LOCAL7', _('Local 7')),
)

DIRECTORY_SERVICE_CHOICES = (
    ('activedirectory', _('Active Directory')),
    ('domaincontroller', _('Domain Controller')),
    ('ldap', _('LDAP')),
    ('nis', _('NIS')),
)


SYS_LOG_LEVEL = (
    ('f_emerg', _('Emergency')),
    ('f_alert', _('Alert')),
    ('f_crit', _('Critical')),
    ('f_err', _('Error')),
    ('f_warning', _('Warning')),
    ('f_notice', _('Notice')),
    ('f_info', _('Info')),
    ('f_debug', _('Debug')),
    ('f_is_debug', _('Is_Debug')),
)


# on|off|ctrl|[!]data|auth|auth+[!]data
FTP_TLS_POLICY_CHOICES = (
    ('on', _('on')),
    ('off', _('off')),
    ('data', _('data')),
    ('!data', _('!data')),
    ('auth', _('auth')),
    ('ctrl', _('ctrl')),
    ('ctrl+data', _('ctrl+data')),
    ('ctrl+!data', _('ctrl+!data')),
    ('auth+data', _('auth+data')),
    ('auth+!data', _('auth+!data'))
)


ZFS_RECORDSIZE = (
    ('512', '512'),
    ('1K', '1K'),
    ('2K', '2K'),
    ('4K', '4K'),
    ('8K', '8K'),
    ('16K', '16K'),
    ('32K', '32K'),
    ('64K', '64K'),
    ('128K', '128K'),
    ('256K', '256K'),
    ('512K', '512K'),
    ('1024K', '1024K'),
)

ZFS_VOLBLOCKSIZE = (
    ('512', '512'),
    ('1K', '1K'),
    ('2K', '2K'),
    ('4K', '4K'),
    ('8K', '8K'),
    ('16K', '16K'),
    ('32K', '32K'),
    ('64K', '64K'),
    ('128K', '128K'),
)

JAIL_TEMPLATE_OS_CHOICES = (
    ('FreeBSD', 'FreeBSD'),
    ('Linux', 'Linux')
)

JAIL_TEMPLATE_ARCH_CHOICES = (
    ('x64', 'x64'),
    ('x86', 'x86')
)


class JAIL_TEMPLATE_CHOICES(object):
    def __iter__(self):
        from freenasUI.jails.models import JailTemplate
        yield ('', '-----')
        for jt in JailTemplate.objects.exclude(jt_system=True):
            yield (jt.jt_name, jt.jt_name)


REPL_CIPHER = (
    ('standard', _('Standard')),
    ('fast', _('Fast')),
    ('disabled', _('Disabled')),
)

SAMBA4_ROLE_CHOICES = (
    # ('auto', 'auto'),
    # ('classic', 'classic primary domain controller'),
    # ('netbios', 'netbios backup domain controller'),
    ('dc', 'active directory domain controller'),
    # ('sdc', 'active directory secondary domain controller'),
    # ('member', 'member server'),
    # ('standalone', 'standalone')
)

SAMBA4_DNS_BACKEND_CHOICES = (
    ('SAMBA_INTERNAL', 'SAMBA_INTERNAL'),
    ('BIND9_FLATFILE', 'BIND9_FLATFILE'),
    ('BIND9_DLZ', 'BIND9_DLZ'),
    ('NONE', 'NONE')
)

SAMBA4_FOREST_LEVEL_CHOICES = (
    ('2000', '2000'),
    ('2003', '2003'),
    ('2008', '2008'),
    ('2008_R2', '2008_R2'),
    ('2012', '2012'),
    ('2012_R2', '2012_R2')
)

SHARE_TYPE_CHOICES = (
    ('unix', 'UNIX'),
    ('windows', 'Windows'),
    ('mac', 'Mac')
)

CASE_SENSITIVITY_CHOICES = (
    ('sensitive', _('Sensitive')),
    ('insensitive', _('Insensitive')),
    ('mixed', _('Mixed'))
)


class SERIAL_CHOICES(object):

    def __iter__(self):
        try:
            with client as c:
                ports = c.call('system.advanced.serial_port_choices')
        except Exception:
            ports = ['0x2f8']
        for p in ports:
            yield (p, p)


TUNABLE_TYPES = (
    ('loader', _('Loader')),
    ('rc', _('rc.conf')),
    ('sysctl', _('Sysctl')),
)

CERT_TYPE_CA_CHOICES = (
    ('ca', _('Import an existing Certificate Authority')),
    ('internal_ca', _('Create an internal Certificate Authority')),
    ('intermediate_ca', _('Create an intermediate Certificate Authority')),
)

CERT_TYPE_CERTIFICATE_CHOICES = (
    ('cert', _('Import an existing Certificate')),
    ('internal_cert', _('Create an internal Certificate')),
    ('csr', _('Create a Certificate Signing Request')),
)

CERT_KEY_LENGTH_CHOICES = (
    (1024, '1024'),
    (2048, '2048'),
    (4096, '4096')
)

CERT_DIGEST_ALGORITHM_CHOICES = (
    ('SHA1', _('SHA1')),
    ('SHA224', _('SHA224')),
    ('SHA256', _('SHA256')),
    ('SHA384', _('SHA384')),
    ('SHA512', _('SHA512'))
)


class COUNTRY_CHOICES(object):

    def __init__(self):

        self.__country_file = "/etc/iso_3166_2_countries.csv"
        self.__country_columns = None
        self.__country_list = []

        with open(self.__country_file, 'r', encoding='utf8') as csvfile:
            reader = csv.reader(csvfile)

            i = 0
            for row in reader:
                if i != 0:
                    if row[self.__soi] and row[self.__cni] and \
                       row[self.__2li] and row[self.__3li]:
                        self.__country_list.append(row)

                else:
                    self.__country_columns = row
                    self.__soi = self.__get_sort_order_index()
                    self.__cni = self.__get_common_name_index()
                    self.__fni = self.__get_formal_name_index()
                    self.__2li = self.__get_ISO_3166_1_2_letter_code_index()
                    self.__3li = self.__get_ISO_3166_1_3_letter_code_index()

                i += 1

        self.__country_list = sorted(self.__country_list,
                                     key=lambda x: x[self.__cni])

    def __get_index(self, column):
        index = -1

        i = 0
        for c in self.__country_columns:
            if c.lower() == column.lower():
                index = i
                break

            i += 1

        return index

    def __get_sort_order_index(self):
        return self.__get_index('Sort Order')

    def __get_common_name_index(self):
        return self.__get_index('Common Name')

    def __get_formal_name_index(self):
        return self.__get_index('Formal Name')

    def __get_ISO_3166_1_2_letter_code_index(self):
        return self.__get_index('ISO 3166-1 2 Letter Code')

    def __get_ISO_3166_1_3_letter_code_index(self):
        return self.__get_index('ISO 3166-1 3 Letter Code')

    def __iter__(self):
        return iter((c[self.__2li], c[self.__cni])
                    for c in self.__country_list)


class SHELL_CHOICES(object):

    SHELSS = '/etc/shells'

    def __init__(self):
        with open('/etc/shells', 'r') as f:
            shells = list(map(
                str.rstrip,
                [x for x in f.readlines() if x.startswith('/')]
            ))
        self._dict = {}
        for shell in shells + ['/usr/sbin/nologin']:
            self._dict[shell] = os.path.basename(shell)

    def __iter__(self):
        return iter(sorted(list(self._dict.items())))


NSS_INFO_CHOICES = (
    ('sfu', 'sfu'),
    ('sfu20', 'sfu20'),
    ('rfc2307', 'rfc2307')
)

LDAP_SASL_WRAPPING_CHOICES = (
    ('plain', 'plain'),
    ('sign', 'sign'),
    ('seal', 'seal'),
)

LDAP_SCHEMA_CHOICES = (
    ('rfc2307', 'rfc2307'),
    ('rfc2307bis', 'rfc2307bis'),
    # ('IPA', 'IPA'),
    # ('AD', 'AD')
)


class IDMAP_CHOICES(object):

    def __init__(self):
        from freenasUI.directoryservice.models import idmap_to_enum

        self.__idmap_modules_path = '/usr/local/lib/shared-modules/idmap'
        self.__idmap_modules = []
        self.__idmap_exclude = {'passdb', 'hash'}

        if os.path.exists(self.__idmap_modules_path):
            self.__idmap_modules.extend(
                filter(
                    lambda m: idmap_to_enum(m) and m not in self.__idmap_exclude,
                    map(
                        lambda f: f.rpartition('.')[0],
                        os.listdir(self.__idmap_modules_path)
                    )
                )
            )

    def __iter__(self):
        return iter((m, m) for m in sorted(self.__idmap_modules))


class CIFS_VFS_OBJECTS(object):
    def __iter__(self):
        try:
            with client as c:
                cifs_list = c.call('sharing.cifs.vfsobjects_choices')
                for value in sorted(cifs_list):
                    # This is really a fake tuple
                    yield (value, value)
        except Exception:
            yield (None, None)


AFP_MAP_ACLS_CHOICES = (
    ('none', _('None')),
    ('rights', _('Rights')),
    ('mode', _('Mode')),
)


AFP_CHMOD_REQUEST_CHOICES = (
    ('ignore', _('Ignore')),
    ('preserve', _('Preserve')),
    ('simple', _('Simple')),
)


CLOUD_PROVIDERS = (
    ('AMAZON', _('Amazon S3')),
    ('AZURE', _('Azure Blob Storage')),
    ('BACKBLAZE', _('Backblaze B2')),
    ('GCLOUD', _('Google Cloud Storage')),
)


VM_BOOTLOADER = (
    # ('BHYVELOAD', _('Bhyve Load')),
    ('UEFI', _('UEFI')),
    ('UEFI_CSM', _('UEFI-CSM')),
    # ('GRUB', _('Grub')),
)


VM_DEVTYPES = (
    ('NIC', _('Network Interface')),
    ('DISK', _('Disk')),
    ('RAW', _('Raw File')),
    ('CDROM', _('CD-ROM')),
    ('VNC', _('VNC')),
)

VM_NICTYPES = (
    ('E1000', _('Intel e82545 (e1000)')),
    ('VIRTIO', _('VirtIO')),
)

VNC_RESOLUTION = (
    ('1920x1200', _('1920x1200')),
    ('1920x1080', _('1920x1080')),
    ('1600x1200', _('1600x1200')),
    ('1600x900', _('1600x900')),
    ('1280x1024', _('1280x1024')),
    ('1280x720', _('1280x720')),
    ('1024x768', _('1024x768')),
    ('800x600', _('800x600')),
    ('640x480', _('640x480')),
)

VM_DISKMODETYPES = (
    ('AHCI', _('AHCI')),
    ('VIRTIO', _('VirtIO')),
)

S3_MODES = (
    ('local', _('local')),
    ('distributed', _('distributed'))
)

IPMI_IDENTIFY_PERIOD = (
    ('force', _('Indefinitely')),
    ('15', _('15 seconds')),
    ('30', _('30 seconds')),
    ('60', _('1 minute')),
    ('120', _('2 minutes')),
    ('180', _('3 minutes')),
    ('240', _('4 minutes')),
    ('0', _('Turn off')),
)
