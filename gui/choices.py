#+
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

import csv
import cStringIO
import freenasUI.settings
import logging
import os
import re
import sqlite3
import copy

from os import popen
from django.utils.translation import ugettext_lazy as _

log = logging.getLogger('choices')

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
    ('1',   _('Level 1 - Minimum power usage with Standby (spindown)')),
    ('64',  _('Level 64 - Intermediate power usage with Standby')),
    ('127', _('Level 127 - Intermediate power usage with Standby')),
    ('128',
        _('Level 128 - Minimum power usage without Standby (no spindown)')),
    ('192', _('Level 192 - Intermediate power usage without Standby')),
    ('254', _('Level 254 - Maximum performance, maximum power usage')),
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

VolumeType_Choices = (
        ('UFS', 'UFS'),
        ('ZFS', 'ZFS'),
        )

VolumeEncrypt_Choices = (
        (0, _('Unencrypted')),
        (1, _('Encrypted, no passphrase')),
        (2, _('Encrypted, with passphrase')),
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
        ('CP949', 'CP949'),
        ('CP950', 'CP950'),
        ('CP1026', 'CP1026'),
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
        #Those types are not supported by istgt yet
        #('DVD', _('DVD')),
        #('Tape', _('Tape')),
        #('Pass-thru Device', _('Pass')),
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
    ('default@sitelutions.com', 'sitelutions.com'),
    ('default@dnsomatic.com', 'dnsomatic.com'),
    ('ipv6tb@he.net', 'he.net'),
    ('default@tzo.com', 'tzo.com'),
    ('default@dynsip.org', 'dynsip.org'),
    ('default@dhis.org', 'dhis.org'),
    ('default@majimoto.net', 'majimoto.net'),
    ('default@zerigo.com', 'zerigo.com'),
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

ZFS_AtimeChoices = (
        ('inherit', _('Inherit')),
        ('on',      _('On')),
        ('off',     _('Off')),
        )

ZFS_CompressionChoices = (
        ('inherit', _('Inherit')),
        ('off',     _('Off')),
        ('lz4',     _('lz4 (recommended)')),
        ('gzip',    _('gzip (default level, 6)')),
        ('gzip-1',  _('gzip (fastest)')),
        ('gzip-9',  _('gzip (maximum, slow)')),
        ('zle',     _('zle (runs of zeros)')),
        ('lzjb',    _('lzjb (legacy, not recommended)')),
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
class NICChoices(object):
    """Populate a list of NIC choices"""
    def __init__(self, nolagg=False, novlan=False,
            exclude_configured=True, include_vlan_parent=False,
            with_alias=False, nobridge=True, noepair=True):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        # Remove lo0 from choices
        self._NIClist = filter(
            lambda y: y not in ('lo0', 'pfsync0', 'pflog0', 'ipfw0'),
            self._NIClist)
        conn = sqlite3.connect(freenasUI.settings.DATABASES['default']['NAME'])
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
            # The exception to this case is when we are getting the NIC
            # list for the GUI, in which case we want the vlan parents
            # as they may have a valid config on them.
            if not include_vlan_parent:
                try:
                    c.execute("SELECT vlan_pint FROM network_vlan")
                except sqlite3.OperationalError:
                    pass
                else:
                    for interface in c:
                        if interface[0] in self._NIClist:
                            self._NIClist.remove(interface[0])

        if with_alias:
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

        if nobridge:
            for nic in self._NIClist:
                if nic.startswith('bridge'):
                    self._NIClist.remove(nic)

        if noepair:
            niclist = copy.deepcopy(self._NIClist)
            for nic in niclist:
                if nic.startswith('epair'):
                    self._NIClist.remove(nic)


        self.max_choices = len(self._NIClist)

    def remove(self, nic):
        return self._NIClist.remove(nic)

    def __iter__(self):
        return iter((i, i) for i in self._NIClist)


class IPChoices(NICChoices):

    def __init__(
        self,
        ipv4=True,
        ipv6=True,
        nolagg=False,
        novlan=False,
        exclude_configured=False,
        include_vlan_parent=True
    ):
        super(IPChoices, self).__init__(
            nolagg=nolagg,
            novlan=novlan,
            exclude_configured=exclude_configured,
            include_vlan_parent=include_vlan_parent
        )

        self._IPlist = []
        for iface in self._NIClist:
            pipe = popen("/sbin/ifconfig %s" % iface)
            lines = pipe.read().strip().split('\n')
            for line in lines:
                if line.startswith('\tinet6'):
                    if ipv6 is True:
                        self._IPlist.append(line.split(' ')[1])
                elif line.startswith('\tinet'):
                    if ipv4 is True:
                        self._IPlist.append(line.split(' ')[1])
            pipe.close()
            self._IPlist.sort()

    def remove(self, addr):
        return self._IPlist.remove(addr)

    def __iter__(self):
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

class UPSDRIVER_CHOICES(object):
    "Populate choices from /usr/local/etc/nut/driver.list"
    def __iter__(self):
        if os.path.exists("/usr/local/etc/nut/driver.list"):
            with open('/usr/local/etc/nut/driver.list', 'rb') as f:
                d = f.read()
            r = cStringIO.StringIO()
            for line in re.sub(r'[ \t]+', ' ', d, flags=re.M).split('\n'):
                r.write(line.strip() + '\n')
            r.seek(0)
            reader = csv.reader(r, delimiter=' ', quotechar='"')
            for row in reader:
                if len(row) == 0 or row[0].startswith('#'):
                    continue
                if row[-1].find(' (experimental)') != -1:
                    row[-1] = row[-1].replace(' (experimental)', '').strip()
                yield ("$".join([row[-1], row[3]]), "%s (%s)" % (" ".join(row[0:-1]), row[-1]))


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
    """Populate choices from /usr/share/syscons/keymaps/INDEX.keymaps"""
    INDEX = "/usr/share/syscons/keymaps/INDEX.keymaps"

    def __iter__(self):
        if not os.path.exists(self.INDEX):
            return
        with open(self.INDEX, 'r') as f:
            d = f.read()
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
    ('ldap', _('LDAP')),
    ('nt4', _('NT4')),
    ('nis', _('NIS')),
    )


SUPPORT_TYPE_CHOICES = (
    ('type1', _('type1')),
    ('type2', _('type2')),
    ('type3', _('type3')),
    ('type4', _('type4')),
    ('type5', _('type5')),
    )

