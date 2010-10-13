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
# TIMEZONE_CHOICES should be replaced by system timezone info
TIMEZONE_CHOICES = (
        ('america-los_angeles', 'America/Los_Angeles'),
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

MINUTES1_CHOICES = (
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        )
MINUTES2_CHOICES = (
        ('12', '12'),
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        )

MINUTES3_CHOICES = (
        ('24', '24'),
        ('25', '25'),
        ('26', '26'),
        ('27', '27'),
        ('28', '28'),
        ('29', '29'),
        ('30', '30'),
        ('31', '31'),
        ('32', '32'),
        ('33', '33'),
        ('34', '34'),
        ('35', '35'),
        )
MINUTES4_CHOICES = (
        ('36', '36'),
        ('37', '37'),
        ('38', '38'),
        ('39', '39'),
        ('40', '40'),
        ('41', '41'),
        ('42', '42'),
        ('43', '43'),
        ('44', '44'),
        ('45', '45'),
        ('46', '46'),
        ('47', '47'),
        )

MINUTES5_CHOICES = (
        ('48', '48'),
        ('49', '49'),
        ('50', '50'),
        ('51', '51'),
        ('52', '52'),
        ('53', '53'),
        ('54', '54'),
        ('55', '55'),
        ('56', '56'),
        ('57', '57'),
        ('58', '58'),
        ('59', '59'),
        )
HOURS1_CHOICES = (
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        )

HOURS2_CHOICES = (
        ('12', '12'),
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        )
DAYS1_CHOICES = (
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('10', '10'),
        ('11', '11'),
        ('12', '12'),
        )

DAYS2_CHOICES = (
        ('13', '13'),
        ('14', '14'),
        ('15', '15'),
        ('16', '16'),
        ('17', '17'),
        ('18', '18'),
        ('19', '19'),
        ('20', '20'),
        ('21', '21'),
        ('22', '22'),
        ('23', '23'),
        ('24', '24'),
        )
DAYS3_CHOICES = (
        ('25', '25'),
        ('26', '26'),
        ('27', '27'),
        ('28', '28'),
        ('29', '29'),
        ('30', '30'),
        ('31', '31'),
        )

# Code for generating DAYS_CHOICES
# Generate a list of numbers, this example will generate 1 - 31 in increments of 1
temp = [x for x in xrange(1, 32, 1)]

# ok, now we zip up our list into a list of tuples then convert the list to 
# a tuple
DAYS_CHOICES = tuple(zip(temp, temp))


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
        ('ufs', 'UFS'),
        ('zfs', 'ZFS'),
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

class whoChoices:
    """Populate a list of system user choices"""
    def __init__(self):
        # This doesn't work right, lol
        pipe = popen("pw usershow -a | cut -d: -f1")
        self._wholist = pipe.read().strip().split('\n')
        self.max_choices = len(self._wholist)

    def __iter__(self):
        return iter((i, i) for i in self._wholist)

class DiskChoices:
    """Populate a list of disk choices"""
    def __init__(self):
        pipe = popen("/sbin/sysctl -n kern.disks")
        rootdev = popen("""df / | awk '$1 ~ "/" {print $1}'""").read().strip()
        rootdev_base = re.search('(?<=/dev/)[a-z/]*[0-9]*', rootdev)
        self._disklist = pipe.read().strip().split(' ')
        self._disklist = [ x for x in self._disklist if x != rootdev_base.group(0) ]
        self.max_choices = len(self._disklist)

    def __iter__(self):
        return iter((i, i) for i in self._disklist)

## Network|Interface Management
class NICChoices:
    """Populate a list of NIC choices"""
    def __init__(self):
        pipe = popen("/sbin/ifconfig -l")
        self._NIClist = pipe.read().strip().split(' ')
        self.max_choices = len(self._NIClist)

    def __iter__(self):
        return iter((i, i) for i in self._NIClist)

