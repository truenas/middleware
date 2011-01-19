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
import re

RSYNCJob_Choices = (
        ('local', 'local'),
        ('client', 'client'),
        )
YESNO_CHOICES = (
        ('DO NOTHING', 'DO NOTHING'),
        ('YES', 'YES'),
        ('NO', 'NO'),
        )
SMTPAUTH_CHOICES = (
        ('plain', 'Plain'),
        ('ssl', 'SSL'),
        ('tls', 'TLS'),
        )
# GUI protocol choice
PROTOCOL_CHOICES = (
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
        )
# Language for the GUI
LANG_CHOICES = (
        ('english', 'English'),
        )
ZPOOL_CHOICES = (
        ('Basic', 'Basic'),
        ('Mirror', 'Mirror'),
        ('RAID-Z', 'RAID-Z'),
        ('RAID-Z2', 'RAID-Z2'),
        )
EMAILSECURITY_CHOICES = (
        ('None', 'None'),
        ('SSL', 'SSL'),
        ('TLS', 'TLS'),
        )
SWAPTYPE_CHOICES = (
        ('File', 'File'),
        ('Device', 'Device'),
        )
# need to pull in mountpoints here
MOUNTPOINT_CHOICES = (
        ('FAKE', 'FAKE'),
        )
COMMANDSCRIPT_CHOICES = (
        ('PreInit', 'PreInit'),
        ('PostInit', 'PostInit'),
        ('Shutdown', 'Shutdown'),
        )
TOGGLECRON_CHOICES = (
        ('All', 'All'),
        ('Selected', 'Selected'),
        ('Deselected', 'Deselected'),
        )

## Disks|Management
TRANSFERMODE_CHOICES = (
        ('Auto', 'Auto'),
        ('PIO0', 'PIO0'),
        ('PIO1', 'PIO1'),
        ('PIO2', 'PIO2'),
        ('PIO3', 'PIO3'),
        ('PIO4', 'PIO4'),
        ('WDMA0', 'WDMA0'),
        ('WDMA1', 'WDMA1'),
        ('WDMA2', 'WDMA2'),
        ('UDMA16', 'UDMA-16'),
        ('UDMA33', 'UDMA-33'),
        ('UDMA66', 'UDMA-66'),
        ('UDMA100', 'UDMA-100'),
        ('UDMA133', 'UDMA-133'),
        ('SATA150', 'SATA 1.5Gbit/s'),
        ('SATA300', 'SATA 3.0Gbit/s'),
        )
HDDSTANDBY_CHOICES = (
        ('Always On', 'Always On'),
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
        ('Disabled', 'Disabled'),
        ('1', 'Level 1 - Minimum power usage with Standby (spindown)'),
        ('64', 'Level 64 - Intermediate power usage with Standby'),
        ('127', 'Level 127 - Intermediate power usage with Standby'),
        ('128', 'Level 128 - Minimum power usgae without Standby (no spindown)'),
        ('192', 'Level 192 - Intermediate power usage withot Standby'),
        ('254', 'Level 254 - Maximum performance, maximum power usage'),
        )
ACOUSTICLVL_CHOICES = (
        ('Disabled', 'Disabled'),
        ('Minimum', 'Minimum'),
        ('Medium', 'Medium'),
        ('Maximum', 'Maximum'),
        )

temp = [x for x in xrange(0, 12)]
MINUTES1_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(12, 24)]
MINUTES2_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(24, 36)]
MINUTES3_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(36, 48)]
MINUTES4_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(48, 60)]
MINUTES5_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(0, 12)]
HOURS1_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(12, 24)]
HOURS2_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(1, 13)]
DAYS1_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(13, 25)]
DAYS2_CHOICES = tuple(zip(temp, temp))

temp = [x for x in xrange(25, 32)]
DAYS3_CHOICES = tuple(zip(temp, temp))

MONTHS_CHOICES = (
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
        )
WEEKDAYS_CHOICES = (
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuseday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
        )

VolumeType_Choices = (
        ('UFS', 'UFS'),
        ('ZFS', 'ZFS'),
        )
ZFS_Choices = (
        ('single', 'single'),
        ('mirror', 'mirror'),
        ('raidz1', 'raidz1'),
        ('raidz2', 'raidz2'),
        ('spare', 'spare'),
        ('log', 'log'),
        ('cache', 'cache'),
        )
UFS_Choices = (
        ('ufs', 'UFS'),
        )

## Services|CIFS/SMB|Settings
CIFSAUTH_CHOICES = (
        ('Anonymous', 'Anonymous'),
        ('Local User', 'Local User'),
        ('Domain', 'Domain'),
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
        ('1', 'Minimum'),
        ('2', 'Normal'),
        ('3', 'Full'),
        ('10', 'Debug'),
        )

DISKDISCOVERY_CHOICES = (
        ('default', 'Default'),
        ('time-machine', 'Time Machine'),
        )
CASEFOLDING_CHOICES = (
        ('none', 'No case folding'),
        ('lowercaseboth', 'Lowercase names in both directions'),
        ('uppercaseboth', 'Lowercase names in both directions'),
        ('lowercaseclient', 'Client sees lowercase, server sees uppercase'),
        ('uppercaseclient', 'Client sees uppercase, server sees lowercase'),
        )

ISCSI_TARGET_EXTENT_TYPE_CHOICES = (
        ('File', 'File'),
        ('Device', 'Device'),
        ('ZFS Volume', 'ZFS Volume'),
        )

ISCSI_TARGET_TYPE_CHOICES = (
        ('Disk', 'Disk'),
        ('DVD', 'DVD'),
        ('Tape', 'Tape'),
        ('Pass-thru Device', 'Pass'),
        )

DISCOVERYAUTHMETHOD_CHOICES = (
        ('auto', 'Auto'),
        ('chap', 'CHAP'),
        ('mchap', 'Mutual CHAP'),
        )
DISCOVERYAUTHGROUP_CHOICES = (
        ('none', 'None'),
        )


DYNDNSPROVIDER_CHOICES = (
        ('dyndns', 'dyndns.org'),
        ('freedns', 'freedns.afraid.org'),
        ('zoneedit', 'zoneedit.com'),
        ('no-ip', 'no-ip.com'),
        ('easydns', 'easydns.com'),
        ('3322', '3322.org'),
        ('Custom', 'Custom'),
        )
SNMP_CHOICES = (
        ('mibll', 'Mibll'),
        ('netgraph', 'Netgraph'),
        ('hostresources', 'Host resources'),
        ('UCD-SNMP-MIB ', 'UCD-SNMP-MIB'),
        )
UPS_CHOICES = (
        ('lowbatt', 'UPC reaches low battery'),
        ('batt', 'UPS goes on battery'),
        )
BTENCRYPT_CHOICES = (
        ('preferred', 'Preferred'),
        ('tolerated', 'Tolerated'),
        ('required', 'Required'),
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
        ('failover', 'failover'),
        ('fec', 'fec'),
        ('lacp', 'lacp'),
        ('loadbalance', 'loadbalance'),
        ('roundrobin', 'roundrobin'),
        ('none', 'none'),
        )

ZFS_AtimeChoices = (
        ('inherit', 'Inherit'),
        ('on', 'On'),
        ('off', 'off'),
        )

ZFS_CompressionChoices = (
        ('inherit', 'Inherit'),
        ('off', 'off'),
        ('on', 'Default (lzjb)'),
        ('lzjb', 'lzjb'),
        ('gzip', 'gzip (default level, 6)'),
        ('gzip-1', 'gzip (fastest)'),
        ('gzip-9', 'gzip (maximum, slow)'),
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
    def __init__(self):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        self.max_choices = len(self._NIClist)

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

UserShell = (
        ('sh', 'sh'),
        ('csh', 'csh'),
        ('ksh', 'ksh'),
        ('bash', 'bash'),
        )
