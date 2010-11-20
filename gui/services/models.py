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

from django.db import models
from django import forms
from django.contrib.auth.models import User
import datetime
import time
from os import popen
from django.utils.text import capfirst
from django.forms.widgets import RadioFieldRenderer
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
from freenasUI.choices import *
   


class rsyncjob(models.Model):
    rj_type = models.CharField(
            max_length=120, 
            choices=RSYNCJob_Choices, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_path = models.CharField(
            max_length=120, verbose_name="Share Path",
            help_text="Path to be shared."
            )
    rj_server = models.CharField(
            max_length=120, 
            verbose_name="Remote RSYNC server",
            help_text="IP or FQDN address of remote Rsync server."
            )
    rj_who = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="root", 
            verbose_name="Who"
            )
    rj_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    rj_ToggleMinutes = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Minutes"
            )
    rj_Minutes1 = models.CharField(
            max_length=120, 
            choices=MINUTES1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Minutes2 = models.CharField(
            max_length=120, 
            choices=MINUTES2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Minutes3 = models.CharField(
            max_length=120, 
            choices=MINUTES3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Minutes4 = models.CharField(
            max_length=120, 
            choices=MINUTES4_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_ToggleHours = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Hours"
            )
    rj_Hours1 = models.CharField(
            max_length=120, 
            choices=HOURS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Hours2 = models.CharField(
            max_length=120, 
            choices=HOURS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_ToggleDays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Days"
            )
    rj_Days1 = models.CharField(
            max_length=120, 
            choices=DAYS1_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Days2 = models.CharField(
            max_length=120, 
            choices=DAYS2_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_Days3 = models.CharField(
            max_length=120, 
            choices=DAYS3_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_ToggleMonths = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name="Months"
            )
    rj_Months = models.CharField(
            max_length=120, 
            choices=MONTHS_CHOICES, 
            default="(NONE)", 
            verbose_name=""
            )
    rj_ToggleWeekdays = models.CharField(
            max_length=120, 
            choices=TOGGLECRON_CHOICES, 
            default="Selected", 
            verbose_name=""
            )
    rj_Weekdays = models.CharField(
            max_length=120, 
            choices=WEEKDAYS_CHOICES, 
            default="(NONE)", 
            verbose_name="Weekdays"
            )
    rj_recursive = models.BooleanField(
            verbose_name="Recursive")
    rj_times = models.BooleanField(
            verbose_name="Preserve Times")
    rj_compress = models.BooleanField(
            verbose_name="Compress Network Data")
    rj_archive = models.BooleanField(
            verbose_name="Use Archive Mode")
    rj_delete = models.BooleanField(
            verbose_name="Remove Deleted Files")
    rj_quiet = models.BooleanField(
            verbose_name="Less Logging")
    rj_preserveperms = models.BooleanField(
            verbose_name="Preserve Permissions")
    rj_extattr = models.BooleanField(
            verbose_name="Preserve Extended Attributes")
    rj_options = models.CharField(
            max_length=120, 
            verbose_name="Extra options",
            help_text="Extra options to rsync (usually empty)."
            )

class services(models.Model):
    srv_service = models.CharField(
            max_length=120, 
            verbose_name="Service",
            help_text="Name of Service, should be auto-generated at build time"
            )
    srv_enable = models.BooleanField(
            verbose_name="Enable Service")
    class Meta:
        verbose_name = "Services"
    def __unicode__(self):
        return self.srv_service
    def save(self, *args, **kwargs):
        super(services, self).save(*args, **kwargs)

class CIFS(models.Model):
    cifs_srv_netbiosname = models.CharField(
            max_length=120, 
            verbose_name="NetBIOS name"
            )
    cifs_srv_workgroup = models.CharField(
            max_length=120, 
            verbose_name="Workgroup",
            help_text="Workgroup the server will appear to be in when queried by clients (maximum 15 characters)."
            )
    cifs_srv_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True,
            help_text="Server description. This can usually be left blank."
            )
    cifs_srv_doscharset = models.CharField(
            max_length=120, 
            choices=DOSCHARSET_CHOICES, 
            default="CP437", 
            verbose_name="DOS charset"
            )
    cifs_srv_unixcharset = models.CharField(
            max_length=120, 
            choices=UNIXCHARSET_CHOICES, 
            default="UTF-8", 
            verbose_name="UNIX charset"
            )
    cifs_srv_loglevel = models.CharField(
            max_length=120, 
            choices=LOGLEVEL_CHOICES, 
            default="Minimum", 
            verbose_name="Log level"
            )
    cifs_srv_localmaster = models.BooleanField(
            verbose_name="Local Master")
    cifs_srv_timeserver = models.BooleanField(
            verbose_name="Time Server for Domain")
    cifs_srv_guest = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="www", 
            verbose_name="Guest account", 
            help_text="Use this option to override the username ('ftp' by default) which will be used for access to services which are specified as guest. Whatever privileges this user has will be available to any client connecting to the guest service. This user must exist in the password file, but does not require a valid login."
            )
    cifs_srv_filemask = models.CharField(
            max_length=120, 
            verbose_name="File mask", 
            blank=True,
            help_text="Use this option to override the file creation mask (0666 by default)."
            )
    cifs_srv_dirmask = models.CharField(
            max_length=120, 
            verbose_name="Directory mask", 
            blank=True,
            help_text="Use this option to override the directory creation mask (0777 by default)."
            )
    cifs_srv_sendbuffer = models.CharField(
            max_length=120, 
            verbose_name="Send Buffer Size", 
            blank=True,
            help_text="Size of send buffer (64240 by default)."
            )
    cifs_srv_recvbuffer = models.CharField(
            max_length=120, 
            verbose_name="Receive Buffer Size", 
            blank=True,
            help_text="Size of receive buffer (64240 by default)."
            )
    cifs_srv_largerw = models.BooleanField(
            verbose_name="Large RW support")
    cifs_srv_sendfile = models.BooleanField(
            verbose_name="Send files with sendfile(2)")
    cifs_srv_easupport = models.BooleanField(
            verbose_name="EA Support")
    cifs_srv_dosattr = models.BooleanField(
            verbose_name="Support DOS File Attributes")
    cifs_srv_nullpw = models.BooleanField(
            verbose_name="Allow Empty Password")
    cifs_srv_smb_options = models.TextField(
            max_length=120, 
            verbose_name="Auxiliary paramters", 
            blank=True,
            help_text="These parameters are added to [Global] section of smb.conf"
            )

class AFP(models.Model):            
    afp_srv_name = models.CharField(
            max_length=120, 
            verbose_name="Server Name",
            help_text="Name of the server. If this field is left empty the default server is specified."
            )
    afp_srv_guest = models.BooleanField(
            verbose_name="Guess Access",
            help_text="Allows guest access to all apple shares on this box."
            )
    afp_srv_local = models.BooleanField(
            verbose_name="Local Access",
            help_text="Allow users with local accounts to access apple shares on this box."
            )
    afp_srv_ddp = models.BooleanField(
            verbose_name="Enable DDP",
            help_text="Enables DDP support for low-level appletalk access."
            )

class NFS(models.Model):            
    nfs_srv_servers = models.CharField(
            max_length=120, 
            verbose_name="Number of servers",
            help_text="Specifies how many servers to create. There should be enough to handle the maximum level of concurrency from its clients, typically four to six."
            )

class Unison(models.Model):            
    uni_workingdir = models.CharField(
            max_length=120, 
            verbose_name="Working directory", 
            blank=True
            )
    uni_createworkingdir = models.BooleanField(
            verbose_name="Create Mirroed Directory")
    class Meta:
        verbose_name = "Unison"

class iSCSITarget(models.Model):            
    iscsi_basename = models.CharField(
            max_length=120, 
            verbose_name="Base Name",
            help_text="The base name (e.g. iqn.2007-09.jp.ne.peach.istgt) will append the target name that is not starting with 'iqn.' "
            )
    iscsi_discoveryauthmethod = models.CharField(
            max_length=120, 
            choices=DISCOVERYAUTHMETHOD_CHOICES, 
            default='auto', 
            verbose_name="Discovery Auth Method"
            )
    iscsi_discoveryauthgroup = models.CharField(
            max_length=120, 
            choices=DISCOVERYAUTHGROUP_CHOICES, 
            default='none', 
            verbose_name="Discovery Auth Group"
            )
    iscsi_io = models.CharField(
            max_length=120, 
            verbose_name="I/O Timeout",
            help_text="I/O timeout in seconds (30 by default)."
            )
    iscsi_nopinint = models.CharField(
            max_length=120, 
            verbose_name="NOPIN Interval",
            help_text="NOPIN sending interval in seconds (20 by default)."
            )
    iscsi_maxsesh = models.CharField(
            max_length=120, 
            verbose_name="Max. sessions",
            help_text="Maximum number of sessions holding at same time (32 by default)."
            )
    iscsi_maxconnect = models.CharField(
            max_length=120, 
            verbose_name="Max. connections",
            help_text="Maximum number of connections in each session (8 by default)."
            )
    iscsi_firstburst = models.CharField(
            max_length=120, 
            verbose_name="First burst length",
            help_text="iSCSI initial parameter (65536 by default)."
            )
    iscsi_maxburst = models.CharField(
            max_length=120, 
            verbose_name="Max burst length",
            help_text="iSCSI initial parameter (262144 by default)."
            )
    iscsi_maxrecdata = models.CharField(
            max_length=120, 
            verbose_name="Max receive data segment length",
            help_text="iSCSI initial parameter (262144 by default)."
            )
    iscsi_toggleluc = models.BooleanField(
            verbose_name="Enable LUC")

class DynamicDNS(models.Model):            
    ddns_provider = models.CharField(
            max_length=120, 
            choices=DYNDNSPROVIDER_CHOICES, 
            default='dyndns', 
            verbose_name="Provider"
            )
    ddns_domain = models.CharField(
            max_length=120, 
            verbose_name="Domain name", 
            blank=True,
            help_text="A host name alias. This option can appear multiple times, for each domain that has the same IP. Use a space to separate multiple alias names."
            )
    ddns_username = models.CharField(
            max_length=120, 
            verbose_name="Username"
            )
    ddns_password = models.CharField(
            max_length=120, 
            verbose_name="Password"
            ) # need to make this a 'password' field, but not available in django Models 
    ddns_updateperiod = models.CharField(
            max_length=120, 
            verbose_name="Update period", 
            blank=True
            )
    ddns_fupdateperiod = models.CharField(
            max_length=120, 
            verbose_name="Forced update period", 
            blank=True
            )
    ddns_wildcard = models.BooleanField(
            verbose_name="Enable Wildcard Records")
    ddns_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 

class SNMP(models.Model):
    snmp_location = models.CharField(
            max_length=120, 
            verbose_name="Location", 
            blank=True,
            help_text="Location information, e.g. physical location of this system: 'Floor of building, Room xyzzy'."
            )
    snmp_contact = models.CharField(
            max_length=120, 
            verbose_name="Contact", 
            blank=True,
            help_text="Contact information, e.g. name or email of the person responsible for this system: 'admin@email.address'."
            )
    snmp_community = models.CharField(
            max_length=120, 
            verbose_name="Community",
            help_text="In most cases, 'public' is used here."
            )
    snmp_traps = models.BooleanField(
            verbose_name="Send SNMP Traps")
    snmp_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 

class UPS(models.Model):            
    ups_identifier = models.CharField(
            max_length=120, 
            verbose_name="Identifier",
            help_text="This name is used to uniquely identify your UPS on this system."
            )
    ups_driver = models.CharField(
            max_length=120, 
            verbose_name="Driver", 
            blank=True,
            help_text="The driver used to communicate with your UPS."
            )
    ups_port = models.CharField(
            max_length=120, 
            verbose_name="Port", 
            blank=True,
            help_text="The serial or USB port where your UPS is connected."
            )
    ups_options = models.TextField(
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters will be added to global settings in inadyn.conf."
            ) 
    ups_description = models.CharField(
            max_length=120, 
            verbose_name="Description", 
            blank=True
            )
    ups_shutdown = models.CharField(
            max_length=120, 
            choices=UPS_CHOICES, 
            default='batt', 
            verbose_name="Shutdown mode"
            )
    ups_shutdowntimer = models.CharField(
            max_length=120, 
            verbose_name="Shutdown timer",
            help_text="The time in seconds until shutdown is initiated. If the UPS happens to come back before the time is up the shutdown is canceled."
            )
    ups_rmonitor = models.BooleanField(
            verbose_name="Remote Monitor")
    ups_emailnotify = models.BooleanField(
            verbose_name="Send Email Status Updates")
    ups_toemail = models.CharField(
            max_length=120, 
            verbose_name="To email", 
            blank=True,
            help_text="Destination email address. Separate email addresses by semi-colon."
            )
    ups_subject = models.CharField(
            max_length=120, 
            verbose_name="To email",
            help_text="The subject of the email. You can use the following parameters for substitution:<br /><ul><li>%d - Date</li><li>%h - Hostname</li></ul>"
            )

class Webserver(models.Model):            
    web_protocol = models.CharField(
            max_length=120, 
            choices=PROTOCOL_CHOICES, 
            default='OFF', 
            verbose_name="Protocol"
            )
    web_port = models.CharField(
            max_length=120, 
            verbose_name="Port",
            help_text="TCP port to bind the server to."
            )
    web_docroot = models.CharField(
            max_length=120, 
            verbose_name="Document root",
            help_text="Document root of the webserver. Home of the web page files."
            )
    web_auth = models.BooleanField(
            verbose_name="Require Login")
    web_dirlisting = models.BooleanField(
            verbose_name="Allow Directory Browsing")

class BitTorrent(models.Model):            
    bt_peerport = models.CharField(
            max_length=120, 
            verbose_name="Peer port",
            help_text="Port to listen for incoming peer connections. Default port is 51413."
            )
    bt_downloaddir = models.CharField(
            max_length=120, 
            verbose_name="Download directory", 
            blank=True,
            help_text="Where to save downloaded data."
            )
    bt_configdir = models.CharField(
            max_length=120, 
            verbose_name="Configuration directory",
            help_text="Alternative configuration directory (usually empty)", 
            blank=True
            )
    bt_portfwd = models.BooleanField(
            verbose_name="Enable Port Forwarding")
    bt_pex = models.BooleanField(
            verbose_name="Enable PEX")
    bt_disthash = models.BooleanField(
            verbose_name="Distribution Hashing Enable")
    bt_encrypt = models.CharField(
            max_length=120, 
            choices=BTENCRYPT_CHOICES, 
            default='preferred',
            verbose_name="Encryption",
            help_text="The peer connection encryption mode.", 
            blank=True
            )
    bt_uploadbw = models.CharField(
            max_length=120, 
            verbose_name="Upload bandwidth",
            help_text="The maximum upload bandwith in KB/s. An empty field means infinity.", 
            blank=True
            )
    bt_downloadbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth",
            help_text="The maximum download bandwith in KiB/s. An empty field means infinity.",
            blank=True
            )
    bt_watchdir = models.CharField(
            max_length=120,
            verbose_name="Watch directory",
            help_text="Directory to watch for new .torrent files.",
            blank=True
            )
    bt_incompletedir = models.CharField(
            max_length=120, 
            verbose_name="Incomplete directory",
            help_text="Directory to incomplete files. An empty field means disable.", 
            blank=True
            )
    bt_umask = models.CharField(
            max_length=120,
            verbose_name="User mask",
            help_text="Use this option to override the default permission modes for newly created files (0002 by default).", 
            blank=True
            )
    bt_options = models.CharField(
            max_length=120, 
            verbose_name="Extra Options", 
            blank=True
            )
    bt_adminport = models.CharField(
            max_length=120, 
            verbose_name="Web admin port",
            help_text="Port to run bittorrent's web administration app on"
            )
    bt_adminauth = models.CharField(
            max_length=120, 
            verbose_name="Authorize Web Interface",
            help_text="When turned on, require authorization before allowing access to the web interface"
            )
    bt_adminuser = models.CharField(
            max_length=120, 
            verbose_name="Web admin username",
            help_text="Username to authenticate to web interface with"
            )
    bt_adminpass = models.CharField(
            max_length=120, 
            verbose_name="Web admin password",
            help_text="Password to authenticate to web interface with"
            )

class FTP(models.Model):            
    ftp_clients = models.CharField(
            max_length=120, 
            verbose_name="Clients",
            help_text="Maximum number of simultaneous clients."
            )
    ftp_ipconnections = models.CharField(
            max_length=120, 
            verbose_name="Connections",
            help_text="Maximum number of connections per IP address (0 = unlimited)."
            )
    ftp_loginattempt = models.CharField(
            max_length=120, 
            verbose_name="Login Attempts",
            help_text="Maximum number of allowed password attempts before disconnection."
            )
    ftp_timeout = models.CharField(
            max_length=120, 
            verbose_name="Timeout",
            help_text="Maximum idle time in seconds."
            )
    ftp_rootlogin = models.BooleanField(
            verbose_name="Allow Root Login")
    ftp_onlyanonymous = models.BooleanField(
            verbose_name="Only Allow Anonymous Login")
    ftp_onlylocal = models.BooleanField(
            verbose_name="Only Allow Local User Login")
    ftp_banner = models.TextField(
            max_length=120, 
            verbose_name="Banner", 
            blank=True,
            help_text="Greeting banner displayed by FTP when a connection first comes in."
            )
    ftp_filemask = models.CharField(
            max_length=120, 
            verbose_name="File mask",
            help_text="Use this option to override the file creation mask (077 by default)."
            )
    ftp_dirmask = models.CharField(
            max_length=120, 
            verbose_name="Directory mask",
            help_text="Use this option to override the file creation mask (077 by default)."
            )
    ftp_fxp = models.BooleanField(
            verbose_name="Enable FXP")
    ftp_resume = models.BooleanField(
            verbose_name="Allow Transer Resumption")
    ftp_defaultroot = models.BooleanField(
            verbose_name="Always Chroot") # Is this right?
    ftp_ident = models.BooleanField(
            verbose_name="Require IDENT Authentication")
    ftp_reversedns = models.BooleanField(
            verbose_name="Require Reverse DNS for IP")
    ftp_masqaddress = models.CharField(
            max_length=120, 
            verbose_name="Masquerade address", 
            blank=True,
            help_text="Causes the server to display the network information for the specified IP address or DNS hostname to the client, on the assumption that that IP address or DNS host is acting as a NAT gateway or port forwarder for the server."
            )
    ftp_passiveportsmin = models.CharField(
            max_length=120, 
            verbose_name="Passive ports",
            help_text="The minimum port to allocate for PASV style data connections (0 = use any port)."
            )
    ftp_passiveportsmax = models.CharField(
            max_length=120, 
            verbose_name="Passive ports",
            help_text="The maximum port to allocate for PASV style data connections (0 = use any port). Passive ports restricts the range of ports from which the server will select when sent the PASV command from a client. The server will randomly choose a number from within the specified range until an open port is found. The port range selected must be in the non-privileged range (eg. greater than or equal to 1024). It is strongly recommended that the chosen range be large enough to handle many simultaneous passive connections (for example, 49152-65534, the IANA-registered ephemeral port range)."
            )
    ftp_localuserbw = models.CharField(
            max_length=120, 
            verbose_name="User bandwidth", 
            blank=True,
            help_text="Local user upload bandwith in KB/s. An empty field means infinity."
            )
    ftp_localuserdlbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Local user download bandwith in KB/s. An empty field means infinity."
            )
    ftp_anonuserbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Anonymous user upload bandwith in KB/s. An empty field means infinity."
            )
    ftp_anonuserdlbw = models.CharField(
            max_length=120, 
            verbose_name="Download bandwidth", 
            blank=True,
            help_text="Anonymous user download bandwith in KB/s. An empty field means infinity."
            )
    ftp_ssltls = models.BooleanField(
            verbose_name="Enable SSL/TLS")
    ftp_options = models.TextField(
            max_length=120, 
            verbose_name="Auxiliary parameters", 
            blank=True,
            help_text="These parameters are added to proftpd.conf."
            )

class TFTP(models.Model):            
    tftp_directory = models.CharField(
            max_length=120, 
            verbose_name="Directory",
            help_text="The directory containing the files you want to publish. The remote host does not need to pass along the directory as part of the transfer."
            )
    tftp_newfiles = models.BooleanField(
            verbose_name="Allow New Files")
    tftp_port = models.CharField(
            max_length=120, 
            verbose_name="Port",
            help_text="The port to listen to. The default is to listen to the tftp port specified in /etc/services."
            )
    tftp_username = models.CharField(
            max_length=120, 
            choices=whoChoices(), 
            default="nobody", 
            verbose_name="Username", 
            help_text="Specifies the username which the service will run as."
            )
    tftp_umask = models.CharField(
            max_length=120, 
            verbose_name="umask",
            help_text="Set the umask for newly created files to the specified value. The default is 022 (everyone can read, nobody can write)."
            )
    tftp_options = models.CharField(
            max_length=120, 
            verbose_name="Extra options",
            blank=True, 
            help_text="Extra command line options (usually empty)."
            )

class SSH(models.Model):            
    ssh_tcpport = models.CharField(
            max_length=120, 
            verbose_name="TCP Port",
            help_text="Alternate TCP port. Default is 22"
            )
    ssh_rootlogin = models.BooleanField(
            verbose_name="Login as Root with password",
            help_text="Disabled: Root can only login via public key authentication; Enabled: Root login permitted with password"
            )
    ssh_passwordauth = models.BooleanField(
            verbose_name="Allow Password Authentication")
    ssh_tcpfwd = models.BooleanField(
            verbose_name="Allow TCP Port Forwarding")
    ssh_compression = models.BooleanField(
            verbose_name="Compress Connections")
    ssh_privatekey = models.TextField(
            max_length=1024,
            verbose_name="Host Private Key", 
            blank=True,
            help_text="Paste a RSA PRIVATE KEY in PEM format here."
            )
    ssh_options = models.TextField(
            max_length=120, 
            verbose_name="Extra options", 
            blank=True,
            help_text="Extra options to /etc/ssh/sshd_config (usually empty). Note, incorrect entered options prevent SSH service to be started."
            )
  
class ActiveDirectory(models.Model):            
    ad_dcname = models.CharField(
            max_length=120, 
            verbose_name="Domain Controller Name",
            help_text="AD or PDC name."
            )
    ad_domainname = models.CharField(
            max_length=120, 
            verbose_name="Domain Name (DNS/Realm-Name)",
            help_text="Domain Name, eg example.com"
            )
    ad_netbiosname = models.CharField(
            max_length=120,
            verbose_name="Domain Name (NetBIOS-Name)",
            help_text="Domain Name in old format, eg EXAMPLE"
            )
    ad_adminname = models.CharField(
            max_length=120, 
            verbose_name="Administrator Name",
            help_text="Username of Domain Administrator Account"
            )
    ad_adminpw = models.CharField(
            max_length=120, 
            verbose_name="Administrator Password",
            help_text="Password of Domain Administrator account."
            )

class LDAP(models.Model):            
    ldap_hostname = models.CharField(
            max_length=120, 
            verbose_name="Hostname", 
            blank=True,
            help_text="The name or IP address of the LDAP server"
            )
    ldap_basedn = models.CharField(
            max_length=120, 
            verbose_name="Base DN",
            blank=True,
            help_text="The default base Distinguished Name (DN) to use for seraches, eg dc=test,dc=org"
            )
    ldap_anonbind = models.BooleanField(
            verbose_name="Allow Anonymous Binding")
    ldap_rootbasedn = models.CharField(
            max_length=120, 
            verbose_name="Root bind DN", 
            blank=True,
            help_text="The distinguished name with which to bind to the directory server, e.g. cn=admin,dc=test,dc=org"
            )
    ldap_rootbindpw = models.CharField(
            max_length=120, 
            verbose_name="Root bind password",
            blank=True,
            help_text="The credentials with which to bind."
            )
    ldap_pwencryption = models.CharField(
            max_length=120, 
            choices=PWEncryptionChoices, 
            verbose_name="Password Encryption",
            help_text="The password change protocol to use."
            )
    ldap_usersuffix = models.CharField(
            max_length=120, 
            verbose_name="User Suffix",
            blank=True,
            help_text="This parameter specifies the suffix that is used for users when these are added to the LDAP directory, e.g. ou=Users"
            )
    ldap_groupsuffix = models.CharField(
            max_length=120, 
            verbose_name="Group Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for groups when these are added to the LDAP directory, e.g. ou=Groups"
            )
    ldap_passwordsuffix = models.CharField(
            max_length=120, 
            verbose_name="Password Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for passwords when these are added to the LDAP directory, e.g. ou=Passwords"
            )
    ldap_machinesuffix = models.CharField(
            max_length=120, 
            verbose_name="Machine Suffix", 
            blank=True,
            help_text="This parameter specifies the suffix that is used for machines when these are added to the LDAP directory, e.g. ou=Computers"
            )
    ldap_options = models.TextField(
            max_length=120,
            verbose_name="Auxillary Parameters",
            blank=True,
            help_text="These parameters are added to ldap.conf."
            )
