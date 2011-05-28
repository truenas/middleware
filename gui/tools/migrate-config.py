#!/usr/local/bin/python
#- 
# Copyright (c) 2011 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import os
import sys
import sqlite3

from xml.dom import minidom

FREENAS_ETC_BASE = "/conf/base/etc"
FREENAS_RCCONF = os.path.join(FREENAS_ETC_BASE, "rc.conf")
FREENAS_SYSCTLCONF = os.path.join(FREENAS_ETC_BASE, "sysctl.conf")
FREENAS_HOSTSALLOW = os.path.join(FREENAS_ETC_BASE, "hosts.allow")
FREENAS_HOSTS = os.path.join(FREENAS_ETC_BASE, "hosts")

#FREENAS_DBPATH = "/data/freenas-v1.db"
FREENAS_DBPATH = "/home/john/freenas-v1.db"
FREENAS_DEBUG = 1


def usage():
    print >> sys.stderr, "%s <config.xml>" % sys.argv[0]
    sys.exit(1)


class FreeNASSQL:
    def __init__(self, database, debug = 0):
        self.__handle = sqlite3.connect(database)
        self.__cursor = self.__handle.cursor()
        self.__debug = debug

    def sqldebug(self, fmt, *args):
        if self.__debug:
            __str = "DEBUG: " + fmt
            __str = __str % args
            print >> sys.stderr, __str

    def getmaxID(self, table, idname = "id"):
        self.__cursor.execute("select max(%s) from %s" % (idname, table))
        __id = self.__cursor.fetchone()
        if __id:  
            __id = __id[0] 
        else:
            __id = -1

        return __id

    def getCount(self, table):
        __count = self.__cursor.execute("select count(*) from %s" % table)
        if __count:
            __count = __count[0]
        else:
            __count = 0

        return __count

    def query(self, sql):
        return self.__cursor.execute(sql)

    def insert(self, table, pairs):
        __sql = "insert into %s (" % table
        for p in pairs:
            __sql += "%s, " % p
        __sql = __sql[:-2] + ") values ("
        for p in pairs:
            __sql += "'%s', " % pairs[p]
        __sql = __sql[:-2] + ');'

        self.sqldebug(__sql)

        return self.__cursor.lastrowid

    def update(self, table, id, pairs):
        __sql = "update %s set " % table
        for p in pairs:
            __sql += "%s = '%s', " % (p, pairs[p])
        __sql = __sql[:-2] + ' '
        __sql += "where id = '%d';" % id
           
        self.sqldebug(__sql)

        return id

    def do(self, table, pairs):
        __id = self.getmaxID(table)
       
        if __id > 0:
            return self.update(table, __id, pairs)

        else:
            return self.insert(table, pairs)


    def close(self):
        pass


class ConfigParser:
    def __init__(self, config):
        pass
        self.__config = config
        self.__sql = FreeNASSQL(FREENAS_DBPATH, FREENAS_DEBUG)

    def __getChildNodeValue(self, __parent):
        __node = None

        if __parent and __parent.hasChildNodes():
            for __node in __parent.childNodes:
                if __node.nodeType == __node.ELEMENT_NODE:
                    break 

        __value = None
        if __node:
            __value = __node.nodeValue

        return __value

    def __getChildNode(self, __parent, __name):
        __node = None

        if __parent and __parent.hasChildNodes():
            for __node in __parent.childNodes:
                if (__node.nodeType == __node.ELEMENT_NODE) and (__name != __node.localName):
                    __node = self.__getChildNode(__node, __name)

                elif (__node.nodeType == __node.ELEMENT_NODE) and (__name == __node.localName):
                    break

                else:
                    __node = self.__getChildNode(__node, __name)

        return __node

    def __getChildNodes(self, __parent, __name):
        __nodes = []

        if __parent and __parent.hasChildNodes():
            for __node in __parent.childNodes:
                if __node.nodeType == __node.ELEMENT_NODE and __node.localName == __name:
                    __nodes.append(__node)
        else:
            __node = self.__getChildNode(__parent, __name)
            __nodes.append(__node)

        return __nodes

    def __getNodeByName(self, __top, __parent, __nodename, __name, __value):
       __topnode = self.__getChildNode(__top, __parent)

       __found_node = None
       if __topnode:
           __nodes = self.__getChildNodes(__topnode, __nodename) 
           for __node in __nodes:
               __node_name = self.__getChildNode(__node, __name)
               if __node_name: 
                   __node_name_value = self.__getChildNodeValue(__node_name)
                   if __node_name_value == __value:
                       __found_node = __node
                       break

       return __found_node

    def _nullmethod(self, __parent, __level):
        pass

    def __getmethod(self, __base, __name):
        __method = self._nullmethod

        try:
            if __base:
                __prefix = '_handle_' + __base + '_'
            else: 
                __prefix = '_handle_'

            __method = getattr(self, __prefix + __name)

        except AttributeError:
            print "oops, missing %s" % __prefix + __name
            __method = self._nullmethod

        return __method

    def __do_probe(self, __parent, __level, __depth):
        for __node in __parent.childNodes:
            if __node.hasChildNodes():
                if __level + 1 > __depth['levels']:
                    __depth['levels'] = __level + 1
                self.__do_probe(__node, __level + 1, __depth)

    def __probe(self, __parent, __depth = 1):
        __d = {}
        __d['levels'] = __depth

        self.__do_probe(__parent, 1, __d)
        return __d['levels']

    def __set_pairs(self, __parent, __nodemap, __pairs):
        for __key in __nodemap:
            __node = self.__getChildNode(__parent, __key)
            if not __node:
                continue 

            __value = self.__getChildNodeValue(__node)
            if not __value:
                continue

            if __nodemap[__key]:
                __pairs[__nodemap[__key]] = __value

    #
    # XXX WTF??? XXX
    #
    def _handle_access(self, __parent, __level):
        pass

    def _handle_ad(self, __parent, __level):
        __nodemap = {'domaincontrollername':'ad_dcname', 'domainname_dns':'ad_domainname',
            'domainname_netbios':'ad_netbiosname', 'username':'ad_adminname',
            'password':'ad_adminpw', 'enable':None}

        __pairs = {}
        __table = "services_activedirectory"

        self.__set_pairs(__parent, __nodemap, __pairs)

        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX Not sure I got this one right... XXX
    #
    def _handle_afp(self, __parent, __level):
        __nodemap = {'enable':None, 'afpname':'afp_srv_name', 'guest':'afp_srv_guest'}

        __pairs = {}
        __table = "services_afp"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX Not implemented XXX
    #
    def _handle_bittorrent(self, __parent, __level):
        pass

    def _handle_cron(self, __parent, __level):
        __nodemap = {'enable':None, 'desc':None, 'all_mins':None,
            'all_hours':None, 'all_days':None, 'all_months':None,
            'all_weekdays':None, 'minute':'cron_minute', 'hour':'cron_hour',
            'day':'cron_daymonth', 'month':'cron_month', 'weekday':'cron_dayweek',
            'who':'cron_user', 'command':'cron_command'}

        __table = "services_cronjob"
        __job_nodes = self.__getChildNodes(__parent, "job")
        for __job_node in __job_nodes:
            __pairs = {}

            self.__set_pairs(__job_node, __nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)

    #
    # XXX Not implemented XXX
    #
    def _handle_daap(self, __parent, __level):
        pass

    #
    # XXX WTF??? XXX
    #
    def _handle_diag(self, __parent, __level):
        pass

    #
    # XXX this needs more work XXX
    #
    def _handle_disks(self, __parent, __level):
        __nodemap = {'name':'disk_name', 'devicespecialfile':'disk_disks',
            'harddiskstandby':'disk_hddstandby', 'acoustic':'disk_acousticlevel',
            'apm':None, 'transfermode':'disk_transfermode', 'type':None,
            'desc':'disk_description', 'size':None, 'smart':None, 'fstype':None}

        __disk_nodes = self.__getChildNodes(__parent, "disk")
        for __disk_node in __disk_nodes:

            __pairs = {}
            __table = "storage_disk"

            self.__set_pairs(__disk_node, __nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)

    #
    # XXX This needs to be implemented XXX
    #
    def _handle_dynamicdns(self, __parent, __level):
        __nodemap = {'enable':None, 'provider':'ddns_provider',
            'domainname':'ddns_domain', 'username':'ddns_username',
            'password':'ddns_password', 'updateperiod':'ddns_updateperiod',
            'forcedupdateperiod':'ddns_fupdateperiod', 'wildcard':None, 'auxparam':None}

        __pairs = {} 
        __table = "services_dynamicdns"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs)
             

    #
    # XXX Hopefully this is correct XXX
    #
    def _handle_ftpd(self, __parent, __level):
        __nodemap = {'numberclients':'ftp_clients',
            'maxconperip':'ftp_ipconnections',
            'maxloginattempts':'ftp_loginattempt',
            'timeout':'ftp_timeout',
            'port':'ftp_port',
            'pasv_max_port':'ftp_passiveportsmax',
            'pasv_min_port':'ftp_passiveportsmin',
            'pasv_address':'ftp_masqaddress',
            'directorymask':'ftp_dirmask',
            'filemask':'ftp_filemask',
            'chrooteveryone':None,
            'privatekey':None,
            'certificate':None,
            'userbandwidth':None,
            'anonymousbandwidth':None,
            'banner':'ftp_banner',
            'tlsrequired':'ftp_ssltls'}

        __pairs = {}
        __table = "services_ftp"
        for __key in __nodemap:
            __node = self.__getChildNode(__parent, __key)
            if not __node:
                continue

            if __key == 'userbandwidth' or __key == 'anonymousbandwidth':
                if __key == 'userbandwidth':
                    __subnodemap = {'up':'ftp_localuserbw', 'down':'ftp_localuserdlbw'}
                else:
                    __subnodemap = {'up':'ftp_anonuserbw', 'down':'ftp_anonuserdlbw'}

                for __subkey in __subnodemap:
                    __subnode = self.__getChildNode(__node, __subkey)
                    if not __subnode:
                        continue

                    __subvalue = self.__getChildNodeValue(__subnode)
                    if not __subvalue:
                        continue

                    if __subnodemap[__subkey]:
                        __pairs[__subnodemap[__subkey]] = __subvalue

            else:
                __value = self.__getChildNodeValue(__node)
                if not __value:
                    continue

                if __nodemap[__key]:
                    __pairs[__nodemap[__key]] = __value

        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gconcat(self, __parent, __level):
        pass

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_geli(self, __parent, __level):
        pass

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gmirror(self, __parent, __level):
        pass

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_graid5(self, __parent, __level):
        pass

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gstripe(self, __parent, __level):
        pass

    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gvinum(self, __parent, __level):
        pass

    #
    # XXX not sure what to do with gateway on this one, default? static route?  XXX
    #
    def _handle_interfaces(self, __parent, __level):
        __nodemap = {'enable':None, 'if':'int_interface', 'ipaddr':'int_ipv4address',
             'subnet':'int_v4netmaskbit', 'ipv6addr':'int_ipv6address',
            'ipv6subnet':'int_v6netmaskbit', 'media':None, 'mediaopt':'int_options', 'gateway':None}

        __table = "network_interfaces"
        __lan_nodes = self.__getChildNodes(__parent, "lan")
        for __lan_node in __lan_nodes:

            __pairs = {}
            for __key in __nodemap:
                __node = self.__getChildNode(__lan_node, __key)

                __value = None 
                if __node:
                    __value = self.__getChildNodeValue(__node)

                if __key == 'ipaddr' and __value == 'dhcp':
                    __value = None
                    __pairs['int_dhcp'] = 1

                elif __key == 'ipv6addr' and __value == 'auto':
                    __value = None
                    __pairs['int_ipv6auto'] = 1

                if __nodemap[__key]:
                    __pairs[__nodemap[__key]] = __value

            if __pairs:
                self.__sql.insert(__table, __pairs) 

    #
    # XXX these are icky, come back to later XXX
    #
    def _handle_iscsiinit(self, __parent, __level):
        pass

    def _handle_iscsitarget(self, __parent, __level):


        #
        # iSCSI tables:
        #
        # services_iscsitarget
        # services_iscsitargetauthcredential
        # services_iscsitargetauthorizedinitiator
        # X services_iscsitargetextent
        # X services_iscsitargetglobalconfiguration
        # X services_iscsitargetportal
        # services_iscsitargettoextent
        #


        __table = "services_iscsitargetglobalconfiguration"
        __iscsi_nodemap = {'enable':None, 'nodebase':'iscsi_basename',
            'discoveryauthmethod':'iscsi_discoveryauthmethod', 
            'discoveryauthgroup':'iscsi_discoveryauthgroup', 'timeout':'iscsi_iotimeout',
            'nopininterval':'iscsi_nopinint', 'maxsessions':'iscsi_maxsesh',
            'maxconnections':'iscsi_maxconnect', 'firstburstlength':'iscsi_firstburst',
            'maxburstlength':'iscsi_maxburst', 'maxrecvdatasegmentlength':'iscsi_maxrecdata'}
        __pairs = {}

        self.__set_pairs(__parent, __iscsi_nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs)


        __table = "services_iscsitargetportal"
        __portalgroup_nodemap = {'tag':'iscsi_target_portal_tag',
            'comment':'iscsi_target_portal_comment', 'portal':'iscsi_target_portal_listen' }
        __portalgroup_nodes = self.__getChildNodes(__parent, "portalgroup")
        for __portalgroup_node in __portalgroup_nodes:
            __pairs = {}

            self.__set_pairs(__portalgroup_node, __portalgroup_nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)
            

        #__table = "services_iscsitargetauthorizedinitiator"
        #__initialgroup_nodemap = {'tag':'iscsi_target_initiator_tag',
        #    'comment':'iscsi_target_initiator_comment', 'iginitiatorname':'', 'ignetmask':''}
        #__initialgroup_nodes = self.__getChildNodes(__parent, "initiatorgroup")
        #for __initialgroup_node in __initialgroup_nodes:
        #    for __key in __initialgroup_nodemap:
        #        pass


        __table = "services_iscsitargetauthcredential"
        __authgroup_nodemap = {'tag':'iscsi_target_auth_tag', 'comment':None }
        __agauth_nodemap = { 'authuser':'iscsi_target_auth_user',
            'authsecret':'iscsi_target_auth_secret', 'authmuser':'iscsi_target_auth_peeruser',
            'authmsecret':'iscsi_target_auth_peersecret' }

        __authgroup_nodes = self.__getChildNodes(__parent, "authgroup")
        for __authgroup_node in __authgroup_nodes:
            __pairs = {}
            self.__set_pairs(__authgroup_node, __authgroup_nodemap, __pairs)

            __agauth_nodes = self.__getChildNodes(__authgroup_node, "agauth")
            for __agauth_node in __agauth_nodes:
                self.__set_pairs(__agauth_node, __agauth_nodemap, __pairs) 

        if __pairs:
            self.__sql.insert(__table, __pairs)


        __table = "services_iscsitargetextent"
        __extent_nodemap = {'name':'iscsi_target_extent_name', 'path':'iscsi_target_extent_path',
            'size':'iscsi_target_extent_filesize', 'type':'iscsi_target_extent_type',
            'comment':'iscsi_target_extent_comment' }
        __extent_nodes  = self.__getChildNodes(__parent, "extent")
        for __extent_node in __extent_nodes:
            for __key in __extent_nodemap: 
                __node = self.__getChildNode(__extent_node, __key)
                if not __node:
                    continue

                __value = self.__getChildNodeValue(__node)
                if not __value:
                    continue

                if __key == 'size':
                    __sizeunit_node = self.__getChildNode(__extent_node, "sizeunit")
                    __sizeunit_value = None
                    if __sizeunit_node:
                        __sizeunit_value = self.__getChildNodeValue(__sizeunit_node)
                    if __sizeunit_value:
                        __value = __value + __sizeunit_value

                if __extent_nodemap[__key]:
                    __pairs[__extent_nodemap[__key]] = __value

        if __pairs:
            self.__sql.insert(__table, __pairs)


        #__table = ""
        #__target_nodemap = {'name':'', 'alias':'', 'type':'', 'flags':'', 'comment':'',
        #    'authmethod':'', 'digest':'', 'queuedepth':'', 'inqvendor':'', 'inqproduct':'',
        #    'inqrevision':'', 'inqserial':'', 'pgigmap':'', 'agmap':'', 'lunmap':''}
        #__target_nodes = self.__getChildNodes(__parent, "target")
        #for __target_node in __target_nodes:
        #    pass


    #
    # XXX don't care about this XXX
    #
    def _handle_lastchange(self, __parent, __level):
        pass

    def _handle_ldap(self, __parent, __level):
        __nodemap = {'hostname':'ldap_hostname', 'base':'ldap_basedn', 'anonymousbind':'ldap_anonbind',
            'binddn':None, 'bindpw':None, 'rootbinddn':'ldap_rootbasedn', 'rootbindpw':'ldap_rootbindpw',
            'pam_password':None, 'user_suffix':'ldap_usersuffix', 'group_suffix':'ldap_groupsuffix',
            'password_suffix':'ldap_passwordsuffix', 'machine_suffix':'ldap_machinesuffix'}

        __pairs = {}
        __table = "services_ldap"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs)

    #
    # XXX WTF??? XXX
    #
    def _handle_mounts(self, __parent, __level):
        pass


    #
    # XXX need data XXX
    #
    def _handle_nfsd(self, __parent, __level):
        __nodemap = { 'enable':None, 'numproc':'nfs_srv_servers' }

        __pairs = {}
        __table = "services_nfs"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs)


        __share_nodemap = { 'path':'', 'mapall':'', 'network':'', 'comment':'' }
        __options_nodemap = { 'alldirs':'', 'ro':'', 'quiet':'' }
        __share_nodes = self.__getChildNodes(__parent, "share")
        for __share_node in __share_nodes:

            self.__set_pairs(__share_node, __share_nodemap, __pairs)

            __options_node = self.__getChildNode(__share_node, "options")

    #
    # XXX need data XXX
    #
    def _handle_rc(self, __parent, __level):
        pass

    #
    # XXX this looks like a cron job or something, needs looking into XXX
    #
    def _handle_reboot(self, __parent, __level):
        pass

    #
    # XXX needs to be implemented XXX
    #
    def _handle_rsync(self, __parent, __level):
        pass

    #
    # XXX doesn't migrate? XXX
    #
    def _handle_rsyncd(self, __parent, __level):
        pass

    def _handle_samba(self, __parent, __level):

        __settingsmap = {'netbiosname':'cifs_srv_netbiosname', 'workgroup':'cifs_srv_workgroup',
            'serverdesc':'cifs_srv_description', 'security':'cifs_srv_authmodel',
            'guestaccount':'cifs_srv_guest', 'localmaster':'cifs_srv_localmaster',
            'rcvbuf':None, 'sndbuf':None, 'storedosattributes':'cifs_srv_dosattr',
            'largereadwrite':'cifs_srv_largerw', 'usesendfile':'cifs_srv_sendfile',
            'aiorsize':'cifs_srv_aio_rs', 'aiowsize':'cifs_srv_aio_ws', 'aiowbehind':'',
            'enable':None, 'winssrv':None, 'timesrv':'cifs_srv_timeserver',
            'doscharset':'cifs_srv_doscharset', 'unixcharset':'cifs_srv_unixcharset',
            'loglevel':'cifs_srv_loglevel', 'aio':None}

        __pairs = {}
        __table = "services_cifs"
        for __key in __settingsmap:
            __node = self.__getChildNode(__parent, __key)
            if not __node:
                continue

            __value = self.__getChildNodeValue(__node)
            if not __value:
                continue

            if __settingsmap[__key]:
                __pairs[__settingsmap[__key]] = __value

        if __pairs:
            self.__sql.insert(__table, __pairs)

        __share_pairs = {}
        __share_table = "sharing_cifs_share"
        __sharemap = {'name':'cifs_name', 'path':None, 'comment':'cifs_comment',
            'browseable':'cifs_browsable', 'inheritpermissions':'cifs_inheritperms',
            'recyclebin':'cifs_recyclebin', 'hidedotfiles':None,
            'hostsallow':'cifs_hostsallow', 'hostsdeny':'cifs_hostsdeny'}

        #__mountpoint_table = "storage_mountpoint"

        #
        # Need to figure out logic here, create a volume, then mountpoint,
        # then share is what it looks like on the surface 
        #
        # FreeNAS 0.7 doesn't associate samba shares with disks.... WTF?
        #

        __share_nodes = self.__getChildNodes(__parent, "share") 
        for __share_node in __share_nodes:
            for __key in __sharemap:
                __node = self.__getChildNode(__share_node, __key)
                if not __node:
                    continue

                __value = self.__getChildNodeValue(__node)
                if not __value:
                    continue

                if __sharemap[__key]:
                    __share_pairs[__sharemap[__key]] = __value

            if __share_pairs:
                self.__sql.insert(__share_table, __share_pairs)
            

    #
    # XXX this looks like a cron job or something, needs looking into XXX
    #
    def _handle_shutdown(self, __parent, __level):
        pass

    #
    # XXX Convert to smartd flags for /var/tmp/rc.conf.freenas XXX
    #
    def _handle_smartd(self, __parent, __level):
        pass

    def _handle_snmpd(self, __parent, __level):
        pass

    def _handle_sshd(self, __parent, __level):
        __nodemap = {'port':'ssh_tcpport', 'passwordauthentication':'ssh_passwordauth',
            'pubkeyauthentication':None, 'permitrootlogin':'ssh_rootlogin',
            'enable':None, 'private-key':'ssh_privatekey'}

        __pairs = {}
        __table = "services_ssh"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs) 

    def _handle_staticroutes(self, __parent, __level):
        __nodemap = { 'interface':None, 'network':'sr_destination',
            'gateway':'sr_gateway', 'descr':'sr_description' }

        __table = "network_staticroute"
        __route_nodes = self.__getChildNodes(__parent, "route")
        for __route_node in __route_nodes:
            __pairs = {}

            self.__set_pairs(__route_node, __nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)
        

    #
    # XXX can this be migrated? XXX
    #
    def _handle_statusreport(self, __parent, __level):
        pass

    #
    # XXX need to look at code XXX
    #
    def _handle_syslogd(self, __parent, __level):
        pass

    def _handle_system_hostname(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "network_globalconfiguration"

        __pairs = {}
        __pairs['gc_hostname'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_domain(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "network_globalconfiguration"

        __pairs = {}
        __pairs['gc_domain'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_ipv6dnsserver(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "network_globalconfiguration"

        __pairs = {}
        __pairs['gc_nameserver1'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_username(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "auth_user"

        __pairs = {}
        __pairs['username'] = __value
        __pairs['is_active'] = 1
        __pairs['is_superuser'] = 1
        self.__sql.do(__table, __pairs) 

    def _handle_system_password(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "auth_user"

        __pairs = {}
        __pairs['password'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_timezone(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "system_settings"

        __pairs = {}
        __pairs['stg_timezone'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_language(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "system_settings"

        __pairs = {}
        __pairs['stg_language'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_ntp(self, __parent, __level):
        __node = self.__getChildNode(__parent, "timeservers")
        if not __node:
            return

        __value = self.__getChildNodeValue(__node)
        if not __value:
            return

        __table = "system_settings"

        __pairs = {}
        __pairs['stg_ntpserver1'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_webgui_protocol(self, __parent, __level):
        __node = self.__getChildNode(__parent, "protocol")
        if not __node:
            return

        __value = self.__getChildNodeValue(__node)
        if not __value:
            return

        __table = "system_settings"

        __pairs = {}
        __pairs['stg_guiprotocol'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system_webgui(self, __parent, __level):
        self._handle_system_webgui_protocol(__parent, __level)

        __certificate_node = self.__getChildNode(__parent, "certificate")
        if not __certificate_node:
            return

        __certificate_value = self.__getChildNodeValue(__certificate_node)
        if not __certificate_value:
            return

        __privatekey_node = self.__getChildNode(__parent, "privatekey")
        if not __privatekey_node:
            return

        __privatekey_value = self.__getChildNodeValue(__privatekey_node)
        if not __privatekey_value:
            return

        __table = "system_ssl"

        __value = __privatekey_value + "\n" + __certificate_value + "\n"

        __pairs = {}
        __pairs['ssl_certfile'] = __value
        self.__sql.do(__table, __pairs) 

    #
    # XXX WTF XXX
    #
    def _handle_system_zerconf(self, __parent, __level):
        pass

    def _handle_system_motd(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "system_advanced"

        __pairs = {}
        __pairs['adv_motd'] = __value
        self.__sql.do(__table, __pairs) 

    #
    # XXX how to handle swap ? XXX
    #
    def _handle_system_swap(self, __parent, __level):
        __node = self.__getChildNode(__parent, "type")
        if not __node:
            return

        __value = self.__getChildNodeValue(__node)
        if not __value:
            return

    #
    # XXX no proxy support XXX
    #
    def _handle_system_proxy(self, __parent, __level):
        pass

    def _handle_system_email(self, __parent, __level):
        __nodemap = {'server':'em_outgoingserver', 'port':'em_port', 'security':'em_security',
            'username':'em_user', 'password':'em_pass', 'from':'em_fromemail'}

        __pairs = {}
        __table = "system_email"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX This needs to be implemented XXX
    #
    def _handle_system_rcconf(self, __parent, __level):
        __params = self.__getChildNodes(__parent, "param")

        #f = open(FREENAS_RCCONF, "a")
        for __param in __params:
            __name_node = self.__getChildNode(__param, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __value_node = self.__getChildNode(__param, "value")
            if not __value_node:
                continue

            __value = self.__getChildNodeValue(__value_node)
            if not __value:
                continue

            __comment_node = self.__getChildNode(__param, "comment")
            __comment = None
            if __comment_node:
                __comment = self.__getChildNodeValue(__comment_node)

            __enable_node = self.__getChildNode(__param, "enable")
            __enable = False
            if __enable_node:
                __enable = self.__getChildNodeValue(__enable_node)

        #f.close()

    #
    # XXX Uncomment for real use XXX
    #
    def _handle_system_sysctl(self, __parent, __level):
        __params = self.__getChildNodes(__parent, "param")

        #f = open(FREENAS_SYSCTLCONF, "a")
        for __param in __params:
            __name_node = self.__getChildNode(__param, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __value_node = self.__getChildNode(__param, "value")
            if not __value_node:
                continue

            __value = self.__getChildNodeValue(__value_node)
            if not __value:
                continue

            __comment_node = self.__getChildNode(__param, "comment")
            __comment = None
            if __comment_node:
                __comment = self.__getChildNodeValue(__comment_node)

            #f.write("%s = %s    # %s\n" % (__name, __value, __comment))
            os.write(0, "%s = %s    # %s\n" % (__name, __value, __comment))

        #f.close()

    #
    # XXX Uncomment for real use XXX
    #
    def _handle_system_hosts(self, __parent, __level):
        __host_nodes = self.__getChildNodes(__parent, "hosts")

        #f = open(FREENAS_HOSTS, "a")

        for __host_node in __host_nodes:
            __name_node = self.__getChildNode(__host_node, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __address_node = self.__getChildNode(__host_node, "address")
            if not __address_node:
                continue

            __address = self.__getChildNodeValue(__address_node)
            if not __address:
                continue

            __descr_node = self.__getChildNode(__host_node, "descr")
            __descr = None
            if __descr_node:
                __descr = self.__getChildNodeValue(__descr_node)
            

            __buf = "%s\t%s" % (__address, __name)
            if __descr: 
                __buf += " # %s\n" % __descr

            #f.write(__buf)
            os.write(0, __buf)

        #f.close()

    #
    # XXX This needs to be implemented, just printing out values currently XXX
    #
    def _handle_system_hostsacl(self, __parent, __level):
        __rules = self.__getChildNodes(__parent, "rule")

        #f = open(FREENAS_HOSTSALLOW, "a")
        for __rule in __rules:
            __value = self.__getChildNodeValue(__rule)

        #f.close()

    def _handle_system_usermanagement(self, __parent, __level):
        __group_nodes = self.__getChildNodes(__parent, "group")
        for __node in __group_nodes:
            __id_node = self.__getChildNode(__node, "id")
            if not __id_node:
                continue

            __id = self.__getChildNodeValue(__id_node)
            if not __id:
                continue

            __name_node = self.__getChildNode(__node, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __table = "account_bsdgroups"

            __pairs = {}
            __pairs['bsdgrp_group'] = __name
            __pairs['bsdgrp_gid'] = __id

            self.__sql.insert(__table, __pairs) 

        __user_nodes = self.__getChildNodes(__parent, "user")
        for __node in __user_nodes:
            __name_node = self.__getChildNode(__node, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __id_node = self.__getChildNode(__node, "id")
            if not __id_node:
                continue
            
            __id = self.__getChildNodeValue(__id_node)
            if not __id:
                continue

            __primarygroup_node = self.__getChildNode(__node, "primarygroup")
            if not __primarygroup_node:
                continue

            __primarygroup = self.__getChildNodeValue(__primarygroup_node)
            if not __primarygroup:
                continue

            __table = "account_bsdusers"

            __pairs = {}
            __pairs['bsdusr_username'] =__name
            __pairs['bsdusr_uid'] = __id
            __pairs['bsdusr_group_id'] = __primarygroup

            self.__sql.insert(__table, __pairs) 

            # 
            # XXX This needs to be implemented XXX
            # 
            #__group_nodes = self.__getChildNodes(__node, "group")
            #for __group_node in __group_nodes:
            #    __group_value = self.__getChildNodeValue(__group_node)

            #
            # XXX What should be done with these??? XXX
            #
            #__extraoptions_node = self.__getChildNode(__node, "extraoptions")
            #__extraoptions = self.__getChildNodeValue(__extraoptions_node)

    #
    # XXX convert to pf rules XXX
    #
    def _handle_system_firewall(self, __parent, __level):
        pass

    #
    # XXX needs to be implemented XXX
    #
    def _handle_system_sysconsaver(self, __parent, __level):
        pass

    def _handle_system_dnsserver(self, __parent, __level):
        __value = self.__getChildNodeValue(__parent)
        if not __value:
            return

        __table = "network_globalconfiguration"

        __pairs = {}
        __pairs['gc_nameserver1'] = __value
        self.__sql.do(__table, __pairs) 

    def _handle_system(self, __parent, __level):
        for __node in __parent.childNodes:
            if __node.nodeType == __node.ELEMENT_NODE:
                __method = self.__getmethod("system", __node.localName)
                __method(__node, 0)

    def _handle_tftpd(self, __parent, __level):
        __nodemap = {'dir':'tftp_directory', 'extraoptions':'tftp_options',
            'port':'tftp_port', 'username':'tftp_username', 'umask':'tftp_umask'}

        __pairs = {}
        __table = "services_tftp"

        self.__set_pairs(__parent, __nodemap, __pairs)
        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX WTF??? XXX
    #
    def _handle_unison(self, __parent, __level):
        pass

    #
    # XXX WTF??? XXX
    #
    def _handle_upnp(self, __parent, __level):
        pass

    def _handle_ups(self, __parent, __level):
        __nodemap = {'upsname':'ups_identifier', 'shutdownmode':'ups_shutdown',
            'shutdowntimer':'ups_shutdowntimer', 'email':None}

        __pairs = {}
        __table = "services_ups"
        for __key in __nodemap:
            __node = self.__getChildNode(__parent, __key)
            if not __node:
                continue

            if __key == 'email':
                __subnodemap = {'to':'ups_toemail', 'subject':'ups_subject'}
                for __subkey in __subnodemap:
                    __subnode = self.__getChildNode(__node, __subkey)
                    if not __subnode:
                        continue

                    __subvalue = self.__getChildNodeValue(__subnode)
                    if not __subvalue:
                        continue

                    if __subnodemap[__subkey]:
                        __pairs[__subnodemap[__subkey]] = __subvalue.replace('%', '%%')

            else:
                __value = self.__getChildNodeValue(__node)
                if not __value:
                    continue

                if __nodemap[__key]:
                    __pairs[__nodemap[__key]] = __value

        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX Do we care about this? XXX
    #
    def _handle_version(self, __parent, __level):
        pass

    #
    # XXX Do we care about this? webgui has settings for the django gui XXX
    #
    def _handle_websrv(self, __parent, __level):
        pass

    def __getdisk(self, __parent, __name):
        __disk = {}

        __disk_node = self.__getNodeByName(__parent, "disks", "disk", "name", __name)
        if not __disk_node:
            return None

        __disk_name_node = self.__getChildNode(__disk_node, "name")
        __disk_name = self.__getChildNodeValue(__disk_name_node)
        __disk['name'] = __disk_name

        __disk_devicespecialfile_node = self.__getChildNode(__disk_node, "devicespecialfile")
        __disk_devicespecialfile = self.__getChildNodeValue(__disk_devicespecialfile_node)
        __disk['devicespecialfile'] = __disk_devicespecialfile

        __disk_harddiskstandby_node = self.__getChildNode(__disk_node, "harddiskstandby")
        __disk_harddiskstandby = self.__getChildNodeValue(__disk_harddiskstandby_node)
        __disk['harddiskstandby'] = __disk_harddiskstandby

        __disk_acoustic_node = self.__getChildNode(__disk_node, "acoustic")
        __disk_acoustic = self.__getChildNodeValue(__disk_acoustic_node)
        __disk['acoustic'] = __disk_acoustic

        __disk_apm_node = self.__getChildNode(__disk_node, "apm")
        __disk_apm = self.__getChildNodeValue(__disk_apm_node)
        __disk['apm'] = __disk_apm

        __disk_transfermode_node = self.__getChildNode(__disk_node, "transfermode")
        __disk_transfermode = self.__getChildNodeValue(__disk_transfermode_node)
        __disk['transfermode'] = __disk_transfermode

        __disk_type_node = self.__getChildNode(__disk_node, "type")
        __disk_type = self.__getChildNodeValue(__disk_type_node)
        __disk['type'] = __disk_type

        __disk_desc_node = self.__getChildNode(__disk_node, "desc")
        __disk_desc = self.__getChildNodeValue(__disk_desc_node)
        __disk['desc'] = __disk_desc

        __disk_size_node = self.__getChildNode(__disk_node, "size")
        __disk_size = self.__getChildNodeValue(__disk_size_node)
        __disk['size'] = __disk_size

        __disk_fstype_node = self.__getChildNode(__disk_node, "fstype")
        __disk_fstype = self.__getChildNodeValue(__disk_fstype_node)
        __disk['fstype'] = __disk_fstype

        return __disk


    def __getdataset(self, __parent, __poolname):
        __dataset = {}

        __dataset_node = self.__getNodeByName(__parent, "datasets", "dataset", "pool", __poolname)
        if not __dataset_node:
            return None

        __dataset_name_node = self.__getChildNode(__dataset_node, "name")
        __dataset_name = self.__getChildNodeValue(__dataset_name_node)
        __dataset['name'] = __dataset_name

        __dataset_pool_node = self.__getChildNode(__dataset_node, "pool")
        __dataset_pool = self.__getChildNodeValue(__dataset_pool_node)
        __dataset['pool'] = __dataset_pool

        __dataset_quota_node = self.__getChildNode(__dataset_node, "quota")
        __dataset_quota = self.__getChildNodeValue(__dataset_quota_node)
        __dataset['quota'] = __dataset_quota

        __dataset_readonly_node = self.__getChildNode(__dataset_node, "readonly")
        __dataset_readonly = self.__getChildNodeValue(__dataset_readonly_node)
        __dataset['readonly'] = __dataset_readonly

        __dataset_compression_node = self.__getChildNode(__dataset_node, "compression")
        __dataset_compression = self.__getChildNodeValue(__dataset_compression_node)
        __dataset['compression'] = __dataset_compression

        __dataset_canmount_node = self.__getChildNode(__dataset_node, "canmount")
        __dataset_canmount = self.__getChildNodeValue(__dataset_canmount_node)
        __dataset['canmount'] = __dataset_canmount

        __dataset_xattr_node = self.__getChildNode(__dataset_node, "xattr")
        __dataset_xattr = self.__getChildNodeValue(__dataset_xattr_node)
        __dataset['xattr'] = __dataset_xattr

        __dataset_desc_node = self.__getChildNode(__dataset_node, "desc")
        __dataset_desc = self.__getChildNodeValue(__dataset_desc_node)
        __dataset['desc'] = __dataset_desc

        return __dataset

    #
    # XXX this needs to be implemented XXX
    #
    def _handle_zfs(self, __parent, __level):

        #
        # Do ZFS pools first, for each pool, create a volume. 
        #
        __pools_node = self.__getChildNode(__parent, "pools")
        if __pools_node:
            __table = "storage_volume"

            __pool_nodes = self.__getChildNodes(__pools_node, "pool")
            for __pool_node in __pool_nodes:

                __pool_name_node = self.__getChildNode(__pool_node, "name")
                if not __pool_name_node:
                    continue

                __pool_name = self.__getChildNodeValue(__pool_name_node)
                if not __pool_name:
                    conitnue

                __pool_root_node = self.__getChildNode(__pool_node, "root")
                if not __pool_root_node:
                    continue

                __pool_root = self.__getChildNodeValue(__pool_root_node)
                if not __pool_root:
                    continue

                __pool_mountpoint_node = self.__getChildNode(__pool_node, "mountpoint")
                if not __pool_mountpoint_node:
                    continue

                __pool_mountpoint = self.__getChildNodeValue(__pool_mountpoint_node)
                if not __pool_mountpoint:
                    continue 

                __pool_desc = None
                __pool_desc_node = self.__getChildNode(__pool_node, "desc")
                if __pool_desc_node:
                    __pool_desc = self.__getChildNodeValue(__pool_desc_node)

                __pool_pairs = {}
                __pool_pairs['vol_name'] = __pool_name
                __pool_pairs['vol_fstype'] = "ZFS"
                __volume_id = self.__sql.insert(__table, __pool_pairs) 
                __volume_name = __pool_name

                __pool_vdevices_saved_nodes = []
                __pool_vdevice_nodes = self.__getChildNodes(__pool_node, "vdevice")
                for __pool_vdevice_node in __pool_vdevice_nodes:
                    __pool_vdevice_value = self.__getChildNodeValue(__pool_vdevice_node)

                    __vdevices_node = self.__getChildNode(__parent, "vdevices")
                    if not __vdevices_node:
                        continue

                    __vdevice_nodes = self.__getChildNodes(__vdevices_node, "vdevice")
                    for __vdevice_node in __vdevice_nodes:
                        __vdevice_name_node = self.__getChildNode(__vdevice_node, "name")
                        __vdevice_name = self.__getChildNodeValue(__vdevice_name_node)

                        if __vdevice_name == __pool_vdevice_value:
                            __pool_vdevices_saved_nodes.append(__vdevice_node)
                            break

                __volume_pool_vdevices = {}
                for __pool_vdevice_node in __pool_vdevices_saved_nodes:
                    __vdevice_name_node = self.__getChildNode(__pool_vdevice_node, "name")
                    if not __vdevice_name_node:
                        continue

                    __vdevice_name = self.__getChildNodeValue(__vdevice_name_node)
                    if not __vdevice_name:
                        continue

                    __vdevice_type_node = self.__getChildNode(__pool_vdevice_node, "type")
                    if not __vdevice_type_node:
                        continue

                    __vdevice_type = self.__getChildNodeValue(__vdevice_type_node)
                    if not __vdevice_type:
                        continue

                    if __vdevice_type == 'zraid':
                        __vdevice_type = 'raidz'
                    elif __vdevice_type == 'zraid1':
                        __vdevice_type = 'raidz'
                    elif __vdevice_type == 'zraid2':
                        __vdevice_type = 'raidz2'

                    __vdevice_desc = None
                    __vdevice_desc_node = self.__getChildNode(__pool_vdevice_node, "desc")
                    if __vdevice_desc_node:
                        __vdevice_desc = self.__getChildNodeValue(__vdevice_desc_node)

                    __vdevice_device_nodes = self.__getChildNodes(__pool_vdevice_node, "device")
                    if not __vdevice_device_nodes:
                        continue
 
                    __devices = []
                    for __vdevice_device_node in __vdevice_device_nodes:
                        __vdevice_device_value = self.__getChildNodeValue(__vdevice_device_node)
                        if not __vdevice_device_value:
                            continue

                        __devices.append(__vdevice_device_value)

                    __volume_pool_vdevices[__vdevice_name] = {
                        'type': __vdevice_type,
                        'desc': __vdevice_desc,
                        'devices': __devices
                    }

                #
                # For each pool vdev, create a storage_diskgroup,
                # for each disk in a vdev, create a storage_disk.
                #
                __parentNode = __parent.parentNode
                for __pool_vdevice in __volume_pool_vdevices: 
                    __vdevice = __volume_pool_vdevices[__pool_vdevice]
                     

                    __pairs = {}
                    __table = "storage_diskgroup"
                    if len(__vdevice['devices']) > 1:
                        __pairs['group_name'] = __volume_name + __vdevice['type']
                    else:
                        __pairs['group_name'] = __volume_name

                    __pairs['group_type'] = __vdevice['type']
                    __pairs['group_volume_id'] = __volume_id

                    __diskgroup_id = self.__sql.insert(__table, __pairs)

                    __table = "storage_disk"
                    for __device in __vdevice['devices']:
                        __disk = self.__getdisk(__parentNode, __device)
                        if __disk:
                            __pairs = {
                                'disk_name': __disk['name'],
                                'disk_disks':__disk['name'],
                                'disk_description': __disk['desc'],
                                'disk_transfermode': __disk['transfermode'],
                                'disk_hddstandby': __disk['harddiskstandby'],
                                'disk_advpowermgmt': None,
                                'disk_acousticlevel': __disk['acoustic'],
                                'disk_togglesmart': None,
                                'disk_smartoptions': None,
                                'disk_group_id': __diskgroup_id
                            }

                            self.__sql.insert(__table, __pairs)

                __table = "storage_mountpoint"
                __dataset = self.__getdataset(__parent, __pool_name)
                if __dataset:
                    __pairs = {
                        'mp_path': __pool_root,
                        'mp_ischild': None,
                        'mp_options': None,
                        'mp_volume_id': __volume_id
                    }

                    self.__sql.insert(__table, __pairs)


    def __parse(self, __parent, __level):
        for __node in __parent.childNodes:
            if __node.nodeType == __node.ELEMENT_NODE:
                __method = self.__getmethod(None, __node.localName)
                __method(__node, 0)

    def run(self):
        __doc = minidom.parse(self.__config)
        __root = __doc.documentElement

        __level = 0
        self.__parse(__root, __level)


#
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#
# So this needs a lot of work still. Various methods aren't implemented,
# others probably have some of the field mappings wrong, freenas 0.7
# code needs to be looked at for all possible options, and data 
# validation neeeds to be done for every field. FUN, FUN, FUN. 
#
# Other areas that need work are enabling/disabling services, 
# interfaces, daemons and what not. Various files should be parsed and
# checked before new data is written so that duplicates are avoided, 
# and so on and so on. This is just a rough draft ;-)
#
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#

def main():
    config = None

    try:
        config = sys.argv[1]
    except:
       usage()

    cp = ConfigParser(config)
    cp.run()


if __name__ == '__main__':
    main()
