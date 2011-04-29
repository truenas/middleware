#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from os import popen
from django.utils.translation import ugettext as _
import sqlite3
import freenasUI.settings

SMTPAUTH_CHOICES = (
        ('plain', _('Plain')),
        ('ssl', _('SSL')),
        ('tls', _('TLS')),
        )

# GUI protocol choice
PROTOCOL_CHOICES = (
        ('http', _('HTTP')),
        ('https', _('HTTPS')),
        )

# Language for the GUI
LANG_CHOICES = (
        ('english', _('English')),
        )

## Disks|Management
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
        ('360', '360'),
        )

ADVPOWERMGMT_CHOICES = (
        ('Disabled', _('Disabled')),
        ('1',   _('Level') + ' 1 - ' + _('Minimum power usage with Standby (spindown)')),
        ('64',  _('Level') + ' 64 - ' + _('Intermediate power usage with Standby')),
        ('127', _('Level') + ' 127 - ' + _('Intermediate power usage with Standby')),
        ('128', _('Level') + ' 128 - ' + _('Minimum power usgae without Standby (no spindown)')),
        ('192', _('Level') + ' 192 - ' + _('Intermediate power usage withot Standby')),
        ('254', _('Level') + ' 254 - ' + _('Maximum performance, maximum power usage')),
        )
ACOUSTICLVL_CHOICES = (
        ('Disabled', _('Disabled')),
        ('Minimum', _('Minimum')),
        ('Medium', _('Medium')),
        ('Maximum', _('Maximum')),
        )

temp = [str(x) for x in xrange(0, 12)]
MINUTES1_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(12, 24)]
MINUTES2_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(24, 36)]
MINUTES3_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(36, 48)]
MINUTES4_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(48, 60)]
MINUTES5_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(0, 12)]
HOURS1_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(12, 24)]
HOURS2_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(1, 13)]
DAYS1_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(13, 25)]
DAYS2_CHOICES = tuple(zip(temp, temp))

temp = [str(x) for x in xrange(25, 32)]
DAYS3_CHOICES = tuple(zip(temp, temp))

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
        ('a', _('October')),
        ('b', _('November')),
        ('c', _('December')),
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

VolumeType_Choices = (
        ('UFS', 'UFS'),
        ('ZFS', 'ZFS'),
        )

## Services|CIFS/SMB|Settings
## This will be overrided if LDAP or ActiveDirectory is enabled.
CIFSAUTH_CHOICES = (
        ('share', _('Anonymous')),
        ('user', _('Local User')),
        )
DOSCHARSET_CHOICES = (
        ('CP437', 'CP437'),
        ('CP850', 'CP850'),
        ('CP852', 'CP852'),
        ('CP866', 'CP866'),
        ('CP932', 'CP932'),
        ('CP1251', 'CP1251'),
        ('ASCII', 'ASCII'),
        )
UNIXCHARSET_CHOICES = (
        ('UTF-8', 'UTF-8'),
        ('iso-8859-1', 'iso-8859-1'),
        ('iso-8859-15', 'iso-8859-15'),
        ('gb2312', 'gb2312'),
        ('EUC-JP', 'EUC-JP'),
        ('ASCII', 'ASCII'),
        )
LOGLEVEL_CHOICES = (
        ('1',  _('Minimum')),
        ('2',  _('Normal')),
        ('3',  _('Full')),
        ('10', _('Debug')),
        )

DISKDISCOVERY_CHOICES = (
        ('default', _('Default')),
        ('time-machine', _('Time Machine')),
        )
CASEFOLDING_CHOICES = (
        ('none',            _('No case folding')),
        ('lowercaseboth',   _('Lowercase names in both directions')),
        ('uppercaseboth',   _('Lowercase names in both directions')),
        ('lowercaseclient', _('Client sees lowercase, server sees uppercase')),
        ('uppercaseclient', _('Client sees uppercase, server sees lowercase')),
        )

ISCSI_TARGET_EXTENT_TYPE_CHOICES = (
        ('File',        _('File')),
        ('Device',      _('Device')),
        ('ZFS Volume',  _('ZFS Volume')),
        )

ISCSI_TARGET_TYPE_CHOICES = (
        ('Disk', _('Disk')),
        ('DVD', _('DVD')),
        ('Tape', _('Tape')),
        ('Pass-thru Device', _('Pass')),
        )

ISCSI_TARGET_FLAGS_CHOICES = (
        ('rw', _('read-write')),
        ('ro', _('read-only')),
        )

AUTHMETHOD_CHOICES = (
        ('None',  _('None')),
        ('Auto',  _('Auto')),
        ('CHAP',  _('CHAP')),
        ('CHAP Mutual', _('Mutual CHAP')),
        )
AUTHGROUP_CHOICES = (
        ('None', _('None')),
        )


DYNDNSPROVIDER_CHOICES = (
        ('dyndns@dyndns.org', 'dyndns.org'),
        ('default@freedns.afraid.org', 'freedns.afraid.org'),
        ('default@zoneedit.com', 'zoneedit.com'),
        ('default@no-ip.com', 'no-ip.com'),
        ('default@easydns.com', 'easydns.com'),
        ('dyndns@3322.org', '3322.org'),
        )
SNMP_CHOICES = (
        ('mibll', 'Mibll'),
        ('netgraph', 'Netgraph'),
        ('hostresources', 'Host resources'),
        ('UCD-SNMP-MIB ', 'UCD-SNMP-MIB'),
        )
UPS_CHOICES = (
        ('lowbatt', _('UPS reaches low battery')),
        ('batt', _('UPS goes on battery')),
        )
BTENCRYPT_CHOICES = (
        ('preferred', _('Preferred')),
        ('tolerated', _('Tolerated')),
        ('required',  _('Required')),
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
        ('failover',    'Failover'),
        ('fec',         'FEC'),
        ('lacp',        'LACP'),
        ('loadbalance', 'Load Balance'),
        ('roundrobin',  'Round Robin'),
        ('none',        'None'),
        )

WindowsVersions = (
        ('windows2000', 'Windows 2000'),
        ('windows2003', 'Windows Server 2003'),
        )

ZFS_AtimeChoices = (
        ('inherit', _('Inherit')),
        ('on',      _('On')),
        ('off',     _('Off')),
        )

ZFS_CompressionChoices = (
        ('inherit', _('Inherit')),
        ('off',     _('Off')),
        ('lzjb',    _('lzjb (recommended)')),
        ('gzip',    'gzip (' + _('default level') + ', 6)'),
        ('gzip-1',  'gzip (' + _('fastest') +')'),
        ('gzip-9',  'gzip (' + _('maximum, slow') + ')'),
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

## Network|Interface Management
class NICChoices:
    """Populate a list of NIC choices"""
    def __init__(self, nolagg=False, novlan=False, exclude_configured=True):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        # Remove lo0 from choices
        if 'lo0' in self._NIClist:
            self._NIClist.remove('lo0')
        conn = sqlite3.connect(freenasUI.settings.DATABASE_NAME)
        c = conn.cursor()
        # Remove interfaces that are parent devices of a lagg
        # Database queries are wrapped in try/except as this is run
        # before the database is created during syncdb and the queries
        # will fail
        try:
            c.execute("SELECT lagg_physnic FROM network_lagginterfacemembers")
        except sqlite3.OperationalError:
            pass
        else:
            for interface in c:
                if interface[0] in self._NIClist:
                    self._NIClist.remove(interface[0])

        if nolagg:
            # vlan devices are not valid parents of laggs
            for nic in self._NIClist:
                if nic.startswith('lagg'):
                    self._NIClist.remove(nic)
            for nic in self._NIClist:
                if nic.startswith('vlan'):
                    self._NIClist.remove(nic)
        if novlan:
            for nic in self._NIClist:
                if nic.startswith('vlan'):
                    self._NIClist.remove(nic)
        else:
            # This removes devices that are parents of vlans.  We don't
            # remove these devices if we are adding a vlan since multiple
            # vlan devices may share the same parent.
            try:
                 c.execute("SELECT vlan_pint FROM network_vlan")
            except sqlite3.OperationalError:
                pass
            else:
                for interface in c:
                    if interface[0] in self._NIClist:
                        self._NIClist.remove(interface[0])

        if exclude_configured:
            try:
                # Exclude any configured interfaces
                c.execute("SELECT int_interface FROM network_interfaces "
                          "WHERE int_ipv4address != '' OR int_dhcp != '0' "
                          "OR int_ipv6auto != '0' OR int_ipv6address != ''")
            except sqlite3.OperationalError:
                pass
            else:
                for interface in c:
                    if interface[0] in self._NIClist:
                        self._NIClist.remove(interface[0])

        self.max_choices = len(self._NIClist)

    def remove(self, nic):
        return self._NIClist.remove(nic)

    def __iter__(self):
        return iter((i, i) for i in self._NIClist)

class TimeZoneChoices:
    """Populate timezone from /usr/share/zoneinfo choices"""
    def __init__(self):
        pipe = popen('find /usr/share/zoneinfo/ -type f -not -name zone.tab')
        self._TimeZoneList = pipe.read().strip().split('\n')
        self._TimeZoneList = [ x[20:] for x in self._TimeZoneList ]
        self._TimeZoneList.sort()
        self.max_choices = len(self._TimeZoneList)

    def __iter__(self):
        return iter((i, i) for i in self._TimeZoneList)

v4NetmaskBitList = (
        ('1', '/1 (128.0.0.0)'),
        ('2', '/2 (192.0.0.0)'),
        ('3', '/3 (224.0.0.0)'),
        ('4', '/4 (240.0.0.0)'),
        ('5', '/5 (248.0.0.0)'),
        ('6', '/6 (252.0.0.0)'),
        ('7', '/7 (254.0.0.0)'),
        ('8', '/8 (255.0.0.0)'),
        ('9', '/9 (255.128.0.0)'),
        ('10', '/10 (255.192.0.0)'),
        ('11', '/11 (255.224.0.0)'),
        ('12', '/12 (255.240.0.0)'),
        ('13', '/13 (255.248.0.0)'),
        ('14', '/14 (255.252.0.0)'),
        ('15', '/15 (255.254.0.0)'),
        ('16', '/16 (255.255.0.0)'),
        ('17', '/17 (255.255.128.0)'),
        ('18', '/18 (255.255.192.0)'),
        ('19', '/19 (255.255.224.0)'),
        ('20', '/20 (255.255.240.0)'),
        ('21', '/21 (255.255.248.0)'),
        ('22', '/22 (255.255.252.0)'),
        ('23', '/23 (255.255.254.0)'),
        ('24', '/24 (255.255.255.0)'),
        ('25', '/25 (255.255.255.128)'),
        ('26', '/26 (255.255.255.192)'),
        ('27', '/27 (255.255.255.224)'),
        ('28', '/28 (255.255.255.240)'),
        ('29', '/29 (255.255.255.248)'),
        ('30', '/30 (255.255.255.252)'),
        ('31', '/31 (255.255.255.254)'),
        ('32', '/32 (255.255.255.255)'),
        )

v6NetmaskBitList = (
        ('0', '/0'),
        ('48', '/48'),
        ('60', '/60'),
        ('64', '/64'),
        ('80', '/80'),
        ('96', '/96'),
        )

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
        #('monthly', _('Every these days of month')),
        #('yearly', _('Every these days of specified months')),
        )
