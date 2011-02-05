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

## Services|CIFS/SMB|Settings
## This will be overrided if LDAP or ActiveDirectory is enabled.
CIFSAUTH_CHOICES = (
        ('share', 'Anonymous'),
        ('user', 'Local User'),
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

ISCSI_TARGET_FLAGS_CHOICES = (
        ('rw', 'read-write'),
        ('ro', 'read-only'),
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
        ('failover', 'Failover'),
        ('fec', 'FEC'),
        ('lacp', 'LACP'),
        ('loadbalance', 'Load Balance'),
        ('roundrobin', 'Round Robin'),
        ('none', 'None'),
        )

ZFS_AtimeChoices = (
        ('inherit', 'Inherit'),
        ('on', 'On'),
        ('off', 'Off'),
        )

ZFS_CompressionChoices = (
        ('inherit', 'Inherit'),
        ('off', 'Off'),
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

PermissionChoices = (
    ('Usual ones', (
	('777', 'rwxrwxrwx : World writable'),
	('775', 'rwxrwxr-x : World readable but only owner and group can write'),
	('770', 'rwxrwx--- : Writable only by me and group members'),
	('755', 'rwxr-xr-x : Owner writable and others read only'),
	('750', 'rwxr-x--- : Owner writable and group read only'),
	('700', 'rwx------ : Read/write by owner only, good for home directory'),
     )),
	('776', 'rwxrwxrw-'),
	('774', 'rwxrwxr--'),
	('773', 'rwxrwx-wx'),
	('772', 'rwxrwx-w-'),
	('771', 'rwxrwx--x'),
	('767', 'rwxrw-rwx'),
	('766', 'rwxrw-rw-'),
	('765', 'rwxrw-r-x'),
	('764', 'rwxrw-r--'),
	('763', 'rwxrw--wx'),
	('762', 'rwxrw--w-'),
	('761', 'rwxrw---x'),
	('760', 'rwxrw----'),
	('757', 'rwxr-xrwx'),
	('756', 'rwxr-xrw-'),
	('754', 'rwxr-xr--'),
	('753', 'rwxr-x-wx'),
	('752', 'rwxr-x-w-'),
	('751', 'rwxr-x--x'),
	('750', 'rwxr-x---'),
	('747', 'rwxr--rwx'),
	('746', 'rwxr--rw-'),
	('745', 'rwxr--r-x'),
	('744', 'rwxr--r--'),
	('743', 'rwxr---wx'),
	('742', 'rwxr---w-'),
	('741', 'rwxr----x'),
	('740', 'rwxr-----'),
	('737', 'rwx-wxrwx'),
	('736', 'rwx-wxrw-'),
	('735', 'rwx-wxr-x'),
	('734', 'rwx-wxr--'),
	('733', 'rwx-wx-wx'),
	('732', 'rwx-wx-w-'),
	('731', 'rwx-wx--x'),
	('730', 'rwx-wx---'),
	('727', 'rwx-w-rwx'),
	('726', 'rwx-w-rw-'),
	('725', 'rwx-w-r-x'),
	('724', 'rwx-w-r--'),
	('723', 'rwx-w--wx'),
	('722', 'rwx-w--w-'),
	('721', 'rwx-w---x'),
	('720', 'rwx-w----'),
	('717', 'rwx--xrwx'),
	('716', 'rwx--xrw-'),
	('715', 'rwx--xr-x'),
	('714', 'rwx--xr--'),
	('713', 'rwx--x-wx'),
	('712', 'rwx--x-w-'),
	('711', 'rwx--x--x'),
	('710', 'rwx--x---'),
	('707', 'rwx---rwx'),
	('706', 'rwx---rw-'),
	('705', 'rwx---r-x'),
	('704', 'rwx---r--'),
	('703', 'rwx----wx'),
	('702', 'rwx----w-'),
	('701', 'rwx-----x'),
	('677', 'rw-rwxrwx'),
	('676', 'rw-rwxrw-'),
	('675', 'rw-rwxr-x'),
	('674', 'rw-rwxr--'),
	('673', 'rw-rwx-wx'),
	('672', 'rw-rwx-w-'),
	('671', 'rw-rwx--x'),
	('670', 'rw-rwx---'),
	('667', 'rw-rw-rwx'),
	('666', 'rw-rw-rw-'),
	('665', 'rw-rw-r-x'),
	('664', 'rw-rw-r--'),
	('663', 'rw-rw--wx'),
	('662', 'rw-rw--w-'),
	('661', 'rw-rw---x'),
	('660', 'rw-rw----'),
	('657', 'rw-r-xrwx'),
	('656', 'rw-r-xrw-'),
	('655', 'rw-r-xr-x'),
	('654', 'rw-r-xr--'),
	('653', 'rw-r-x-wx'),
	('652', 'rw-r-x-w-'),
	('651', 'rw-r-x--x'),
	('650', 'rw-r-x---'),
	('647', 'rw-r--rwx'),
	('646', 'rw-r--rw-'),
	('645', 'rw-r--r-x'),
	('644', 'rw-r--r--'),
	('643', 'rw-r---wx'),
	('642', 'rw-r---w-'),
	('641', 'rw-r----x'),
	('640', 'rw-r-----'),
	('637', 'rw--wxrwx'),
	('636', 'rw--wxrw-'),
	('635', 'rw--wxr-x'),
	('634', 'rw--wxr--'),
	('633', 'rw--wx-wx'),
	('632', 'rw--wx-w-'),
	('631', 'rw--wx--x'),
	('630', 'rw--wx---'),
	('627', 'rw--w-rwx'),
	('626', 'rw--w-rw-'),
	('625', 'rw--w-r-x'),
	('624', 'rw--w-r--'),
	('623', 'rw--w--wx'),
	('622', 'rw--w--w-'),
	('621', 'rw--w---x'),
	('620', 'rw--w----'),
	('617', 'rw---xrwx'),
	('616', 'rw---xrw-'),
	('615', 'rw---xr-x'),
	('614', 'rw---xr--'),
	('613', 'rw---x-wx'),
	('612', 'rw---x-w-'),
	('611', 'rw---x--x'),
	('610', 'rw---x---'),
	('607', 'rw----rwx'),
	('606', 'rw----rw-'),
	('605', 'rw----r-x'),
	('604', 'rw----r--'),
	('603', 'rw-----wx'),
	('602', 'rw-----w-'),
	('601', 'rw------x'),
	('600', 'rw-------'),
	('577', 'r-xrwxrwx'),
	('576', 'r-xrwxrw-'),
	('575', 'r-xrwxr-x'),
	('574', 'r-xrwxr--'),
	('573', 'r-xrwx-wx'),
	('572', 'r-xrwx-w-'),
	('571', 'r-xrwx--x'),
	('570', 'r-xrwx---'),
	('567', 'r-xrw-rwx'),
	('566', 'r-xrw-rw-'),
	('565', 'r-xrw-r-x'),
	('564', 'r-xrw-r--'),
	('563', 'r-xrw--wx'),
	('562', 'r-xrw--w-'),
	('561', 'r-xrw---x'),
	('560', 'r-xrw----'),
	('557', 'r-xr-xrwx'),
	('556', 'r-xr-xrw-'),
	('555', 'r-xr-xr-x'),
	('554', 'r-xr-xr--'),
	('553', 'r-xr-x-wx'),
	('552', 'r-xr-x-w-'),
	('551', 'r-xr-x--x'),
	('550', 'r-xr-x---'),
	('547', 'r-xr--rwx'),
	('546', 'r-xr--rw-'),
	('545', 'r-xr--r-x'),
	('544', 'r-xr--r--'),
	('543', 'r-xr---wx'),
	('542', 'r-xr---w-'),
	('541', 'r-xr----x'),
	('540', 'r-xr-----'),
	('537', 'r-x-wxrwx'),
	('536', 'r-x-wxrw-'),
	('535', 'r-x-wxr-x'),
	('534', 'r-x-wxr--'),
	('533', 'r-x-wx-wx'),
	('532', 'r-x-wx-w-'),
	('531', 'r-x-wx--x'),
	('530', 'r-x-wx---'),
	('527', 'r-x-w-rwx'),
	('526', 'r-x-w-rw-'),
	('525', 'r-x-w-r-x'),
	('524', 'r-x-w-r--'),
	('523', 'r-x-w--wx'),
	('522', 'r-x-w--w-'),
	('521', 'r-x-w---x'),
	('520', 'r-x-w----'),
	('517', 'r-x--xrwx'),
	('516', 'r-x--xrw-'),
	('515', 'r-x--xr-x'),
	('514', 'r-x--xr--'),
	('513', 'r-x--x-wx'),
	('512', 'r-x--x-w-'),
	('511', 'r-x--x--x'),
	('510', 'r-x--x---'),
	('507', 'r-x---rwx'),
	('506', 'r-x---rw-'),
	('505', 'r-x---r-x'),
	('504', 'r-x---r--'),
	('503', 'r-x----wx'),
	('502', 'r-x----w-'),
	('501', 'r-x-----x'),
	('500', 'r-x------'),
	('477', 'r--rwxrwx'),
	('476', 'r--rwxrw-'),
	('475', 'r--rwxr-x'),
	('474', 'r--rwxr--'),
	('473', 'r--rwx-wx'),
	('472', 'r--rwx-w-'),
	('471', 'r--rwx--x'),
	('470', 'r--rwx---'),
	('467', 'r--rw-rwx'),
	('466', 'r--rw-rw-'),
	('465', 'r--rw-r-x'),
	('464', 'r--rw-r--'),
	('463', 'r--rw--wx'),
	('462', 'r--rw--w-'),
	('461', 'r--rw---x'),
	('460', 'r--rw----'),
	('457', 'r--r-xrwx'),
	('456', 'r--r-xrw-'),
	('455', 'r--r-xr-x'),
	('454', 'r--r-xr--'),
	('453', 'r--r-x-wx'),
	('452', 'r--r-x-w-'),
	('451', 'r--r-x--x'),
	('450', 'r--r-x---'),
	('447', 'r--r--rwx'),
	('446', 'r--r--rw-'),
	('445', 'r--r--r-x'),
	('444', 'r--r--r--'),
	('443', 'r--r---wx'),
	('442', 'r--r---w-'),
	('441', 'r--r----x'),
	('440', 'r--r-----'),
	('437', 'r---wxrwx'),
	('436', 'r---wxrw-'),
	('435', 'r---wxr-x'),
	('434', 'r---wxr--'),
	('433', 'r---wx-wx'),
	('432', 'r---wx-w-'),
	('431', 'r---wx--x'),
	('430', 'r---wx---'),
	('427', 'r---w-rwx'),
	('426', 'r---w-rw-'),
	('425', 'r---w-r-x'),
	('424', 'r---w-r--'),
	('423', 'r---w--wx'),
	('422', 'r---w--w-'),
	('421', 'r---w---x'),
	('420', 'r---w----'),
	('417', 'r----xrwx'),
	('416', 'r----xrw-'),
	('415', 'r----xr-x'),
	('414', 'r----xr--'),
	('413', 'r----x-wx'),
	('412', 'r----x-w-'),
	('411', 'r----x--x'),
	('410', 'r----x---'),
	('407', 'r-----rwx'),
	('406', 'r-----rw-'),
	('405', 'r-----r-x'),
	('404', 'r-----r--'),
	('403', 'r------wx'),
	('402', 'r------w-'),
	('401', 'r-------x'),
	('400', 'r--------'),
	('377', '-wxrwxrwx'),
	('376', '-wxrwxrw-'),
	('375', '-wxrwxr-x'),
	('374', '-wxrwxr--'),
	('373', '-wxrwx-wx'),
	('372', '-wxrwx-w-'),
	('371', '-wxrwx--x'),
	('370', '-wxrwx---'),
	('367', '-wxrw-rwx'),
	('366', '-wxrw-rw-'),
	('365', '-wxrw-r-x'),
	('364', '-wxrw-r--'),
	('363', '-wxrw--wx'),
	('362', '-wxrw--w-'),
	('361', '-wxrw---x'),
	('360', '-wxrw----'),
	('357', '-wxr-xrwx'),
	('356', '-wxr-xrw-'),
	('355', '-wxr-xr-x'),
	('354', '-wxr-xr--'),
	('353', '-wxr-x-wx'),
	('352', '-wxr-x-w-'),
	('351', '-wxr-x--x'),
	('350', '-wxr-x---'),
	('347', '-wxr--rwx'),
	('346', '-wxr--rw-'),
	('345', '-wxr--r-x'),
	('344', '-wxr--r--'),
	('343', '-wxr---wx'),
	('342', '-wxr---w-'),
	('341', '-wxr----x'),
	('340', '-wxr-----'),
	('337', '-wx-wxrwx'),
	('336', '-wx-wxrw-'),
	('335', '-wx-wxr-x'),
	('334', '-wx-wxr--'),
	('333', '-wx-wx-wx'),
	('332', '-wx-wx-w-'),
	('331', '-wx-wx--x'),
	('330', '-wx-wx---'),
	('327', '-wx-w-rwx'),
	('326', '-wx-w-rw-'),
	('325', '-wx-w-r-x'),
	('324', '-wx-w-r--'),
	('323', '-wx-w--wx'),
	('322', '-wx-w--w-'),
	('321', '-wx-w---x'),
	('320', '-wx-w----'),
	('317', '-wx--xrwx'),
	('316', '-wx--xrw-'),
	('315', '-wx--xr-x'),
	('314', '-wx--xr--'),
	('313', '-wx--x-wx'),
	('312', '-wx--x-w-'),
	('311', '-wx--x--x'),
	('310', '-wx--x---'),
	('307', '-wx---rwx'),
	('306', '-wx---rw-'),
	('305', '-wx---r-x'),
	('304', '-wx---r--'),
	('303', '-wx----wx'),
	('302', '-wx----w-'),
	('301', '-wx-----x'),
	('300', '-wx------'),
	('277', '-w-rwxrwx'),
	('276', '-w-rwxrw-'),
	('275', '-w-rwxr-x'),
	('274', '-w-rwxr--'),
	('273', '-w-rwx-wx'),
	('272', '-w-rwx-w-'),
	('271', '-w-rwx--x'),
	('270', '-w-rwx---'),
	('267', '-w-rw-rwx'),
	('266', '-w-rw-rw-'),
	('265', '-w-rw-r-x'),
	('264', '-w-rw-r--'),
	('263', '-w-rw--wx'),
	('262', '-w-rw--w-'),
	('261', '-w-rw---x'),
	('260', '-w-rw----'),
	('257', '-w-r-xrwx'),
	('256', '-w-r-xrw-'),
	('255', '-w-r-xr-x'),
	('254', '-w-r-xr--'),
	('253', '-w-r-x-wx'),
	('252', '-w-r-x-w-'),
	('251', '-w-r-x--x'),
	('250', '-w-r-x---'),
	('247', '-w-r--rwx'),
	('246', '-w-r--rw-'),
	('245', '-w-r--r-x'),
	('244', '-w-r--r--'),
	('243', '-w-r---wx'),
	('242', '-w-r---w-'),
	('241', '-w-r----x'),
	('240', '-w-r-----'),
	('237', '-w--wxrwx'),
	('236', '-w--wxrw-'),
	('235', '-w--wxr-x'),
	('234', '-w--wxr--'),
	('233', '-w--wx-wx'),
	('232', '-w--wx-w-'),
	('231', '-w--wx--x'),
	('230', '-w--wx---'),
	('227', '-w--w-rwx'),
	('226', '-w--w-rw-'),
	('225', '-w--w-r-x'),
	('224', '-w--w-r--'),
	('223', '-w--w--wx'),
	('222', '-w--w--w-'),
	('221', '-w--w---x'),
	('220', '-w--w----'),
	('217', '-w---xrwx'),
	('216', '-w---xrw-'),
	('215', '-w---xr-x'),
	('214', '-w---xr--'),
	('213', '-w---x-wx'),
	('212', '-w---x-w-'),
	('211', '-w---x--x'),
	('210', '-w---x---'),
	('207', '-w----rwx'),
	('206', '-w----rw-'),
	('205', '-w----r-x'),
	('204', '-w----r--'),
	('203', '-w-----wx'),
	('202', '-w-----w-'),
	('201', '-w------x'),
	('200', '-w-------'),
	('177', '--xrwxrwx'),
	('176', '--xrwxrw-'),
	('175', '--xrwxr-x'),
	('174', '--xrwxr--'),
	('173', '--xrwx-wx'),
	('172', '--xrwx-w-'),
	('171', '--xrwx--x'),
	('170', '--xrwx---'),
	('167', '--xrw-rwx'),
	('166', '--xrw-rw-'),
	('165', '--xrw-r-x'),
	('164', '--xrw-r--'),
	('163', '--xrw--wx'),
	('162', '--xrw--w-'),
	('161', '--xrw---x'),
	('160', '--xrw----'),
	('157', '--xr-xrwx'),
	('156', '--xr-xrw-'),
	('155', '--xr-xr-x'),
	('154', '--xr-xr--'),
	('153', '--xr-x-wx'),
	('152', '--xr-x-w-'),
	('151', '--xr-x--x'),
	('150', '--xr-x---'),
	('147', '--xr--rwx'),
	('146', '--xr--rw-'),
	('145', '--xr--r-x'),
	('144', '--xr--r--'),
	('143', '--xr---wx'),
	('142', '--xr---w-'),
	('141', '--xr----x'),
	('140', '--xr-----'),
	('137', '--x-wxrwx'),
	('136', '--x-wxrw-'),
	('135', '--x-wxr-x'),
	('134', '--x-wxr--'),
	('133', '--x-wx-wx'),
	('132', '--x-wx-w-'),
	('131', '--x-wx--x'),
	('130', '--x-wx---'),
	('127', '--x-w-rwx'),
	('126', '--x-w-rw-'),
	('125', '--x-w-r-x'),
	('124', '--x-w-r--'),
	('123', '--x-w--wx'),
	('122', '--x-w--w-'),
	('121', '--x-w---x'),
	('120', '--x-w----'),
	('117', '--x--xrwx'),
	('116', '--x--xrw-'),
	('115', '--x--xr-x'),
	('114', '--x--xr--'),
	('113', '--x--x-wx'),
	('112', '--x--x-w-'),
	('111', '--x--x--x'),
	('110', '--x--x---'),
	('107', '--x---rwx'),
	('106', '--x---rw-'),
	('105', '--x---r-x'),
	('104', '--x---r--'),
	('103', '--x----wx'),
	('102', '--x----w-'),
	('101', '--x-----x'),
	('100', '--x------'),
	('077', '---rwxrwx'),
	('076', '---rwxrw-'),
	('075', '---rwxr-x'),
	('074', '---rwxr--'),
	('073', '---rwx-wx'),
	('072', '---rwx-w-'),
	('071', '---rwx--x'),
	('070', '---rwx---'),
	('067', '---rw-rwx'),
	('066', '---rw-rw-'),
	('065', '---rw-r-x'),
	('064', '---rw-r--'),
	('063', '---rw--wx'),
	('062', '---rw--w-'),
	('061', '---rw---x'),
	('060', '---rw----'),
	('057', '---r-xrwx'),
	('056', '---r-xrw-'),
	('055', '---r-xr-x'),
	('054', '---r-xr--'),
	('053', '---r-x-wx'),
	('052', '---r-x-w-'),
	('051', '---r-x--x'),
	('050', '---r-x---'),
	('047', '---r--rwx'),
	('046', '---r--rw-'),
	('045', '---r--r-x'),
	('044', '---r--r--'),
	('043', '---r---wx'),
	('042', '---r---w-'),
	('041', '---r----x'),
	('040', '---r-----'),
	('037', '----wxrwx'),
	('036', '----wxrw-'),
	('035', '----wxr-x'),
	('034', '----wxr--'),
	('033', '----wx-wx'),
	('032', '----wx-w-'),
	('031', '----wx--x'),
	('030', '----wx---'),
	('027', '----w-rwx'),
	('026', '----w-rw-'),
	('025', '----w-r-x'),
	('024', '----w-r--'),
	('023', '----w--wx'),
	('022', '----w--w-'),
	('021', '----w---x'),
	('020', '----w----'),
	('017', '-----xrwx'),
	('016', '-----xrw-'),
	('015', '-----xr-x'),
	('014', '-----xr--'),
	('013', '-----x-wx'),
	('012', '-----x-w-'),
	('011', '-----x--x'),
	('010', '-----x---'),
	('007', '------rwx'),
	('006', '------rw-'),
	('005', '------r-x'),
	('004', '------r--'),
	('003', '-------wx'),
	('002', '-------w-'),
	('001', '--------x'),
	('000', '---------'),
)
