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
import getopt
import sqlite3
import re

from xml.dom import minidom

FREENAS_ETC_BASE = "/conf/base/etc"
FREENAS_RCCONF = os.path.join(FREENAS_ETC_BASE, "rc.conf")
FREENAS_SYSCTLCONF = os.path.join(FREENAS_ETC_BASE, "sysctl.conf")
FREENAS_HOSTSALLOW = os.path.join(FREENAS_ETC_BASE, "hosts.allow")
FREENAS_HOSTS = os.path.join(FREENAS_ETC_BASE, "hosts")



def usage():
    print >> sys.stderr, "%s [-d] -c <config.xml> -b <database.db>" % sys.argv[0]
    sys.exit(1)


class FreeNASSQL:
    def __init__(self, database, debug = 0):
        self.__handle = sqlite3.connect(database)
        self.__cursor = self.__handle.cursor()
        self.__debug = debug

    def sqldebug(self, fmt, *args):

        __id = -1
        if self.__debug:
            __str = "DEBUG: " + fmt
            __str = __str % args
            print >> sys.stderr, __str

        else:
            __sql = fmt % args
            self.__cursor.execute(__sql)
            self.__cursor.commit()
            __id = self.__cursor.lastrowid

        return __id

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

        __lastrowid = self.sqldebug(__sql)

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
        self.__cursor.close()


class ConfigParser:
    def __init__(self, config, database, debug = False):
        pass
        self.__config = config
        self.__sql = FreeNASSQL(database, debug)
        self.__failed = False

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
            #print "oops, missing %s" % __prefix + __name
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

    def __fail(self, fmt, *args):
        __str = "FAIL: " + fmt
        __str = __str % args
        print >> sys.stderr, __str


    def __handle_cronjob(self, __parent, __user, __command):
        __enable = self.__getChildNode(__parent, "enable")
        if not __enable: 
            return

        __all_mins_node = self.__getChildNode(__parent, "all_mins")
        if __all_mins_node:
            __all_mins_value = self.__getChildNodeValue(__all_mins_node)
        
        __all_hours_node = self.__getChildNode(__parent, "all_hours")
        if __all_hours_node:
            __all_hours_value = self.__getChildNodeValue(__all_hours_node)

        __all_days_node = self.__getChildNode(__parent, "all_days")
        if __all_days_node:
            __all_days_value = self.__getChildNodeValue(__all_days_node)

        __all_months_node = self.__getChildNode(__parent, "all_months")
        if __all_months_node:
            __all_months_value = self.__getChildNodeValue(__all_months_node)

        __all_weekdays_node = self.__getChildNode(__parent, "all_weekdays")
        if __all_weekdays_node:
            __all_weekdays_value = self.__getChildNodeValue(__all_weekdays_node)

        __minutes_value = ""
        if __all_mins_value:
            __minutes_value = "*"
        else:
            __minute_nodes = self.__getChildNodes(__parent, "minute")
            for __minute_node in __minute_nodes:
                if __minute_node:
                    __minute_value = self.__getChildNodeValue(__minute_node)  
                    __minutes_value += __minute_value + ","
            if __minutes_value:
                __minutes_value = __minutes_value.rstrip(",")

        __hours_value = ""
        if __all_hours_value:
            __hours_value = "*"
        else:
            __hour_nodes = self.__getChildNodes(__parent, "hour")
            for __hour_node in __hour_nodes:
                if __hour_node:
                    __hour_value = self.__getChildNodeValue(__hour_node)
                    __hours_value += __hours_value + ","
            if __hours_value:
                __hours_value = __hours_value.rstrip(",")

        __days_value = ""
        if __all_days_value:
            __days_value = "*"
        else:
            __day_nodes = self.__getChildNodes(__parent, "day")
            for __day_node in __day_nodes:
                if __day_node:
                    __day_value = self.__getChildNodeValue(__day_node)
                    __days_value += __days_value + ","
            if __days_value:
                __days_value = __days_value.rstrip(",")

        __months_value = ""
        if __all_months_value:
            __months_value = "*"
        else:
            __month_nodes = self.__getChildNodes(__parent, "month")
            for __month_node in __month_nodes:
                if __month_node:
                    __month_value = self.__getChildNodeValue(__month_value)
                    __months_value += __months_value + ","
            if __months_value:
                __months_value = __months_value.rstrip(",")

        __weekdays_value = ""
        if __all_weekdays_value:
            __weekdays_value = "*"
        else:
            __weekday_nodes = self.__getChildNodes(__parent, "weekday")
            for __weekday_node in __weekday_nodes:
                if __weekday_node:
                    __weekday_value = self.__getChildNodeValue(__weekday_node)
                    __weekdays_value += __weekdays_value + ","
            if __weekdays_value:
                __weekdays_value = __weekdays_value.rstrip(",")

        __pairs = {}
        __table = "services_cronjob"

        __pairs['cron_minute'] = __minutes_value
        __pairs['cron_hour'] = __hours_value
        __pairs['cron_daymonth'] = __days_value
        __pairs['cron_month'] = __months_value
        __pairs['cron_dayweek'] = __weekdays_value
        __pairs['user'] = __user
        __pairs['command'] = __command

        self.__sql.insert(__table, __pairs)

    #
    # XXX This seems to be user/group creation XXX
    #
    def _handle_access(self, __parent, __level):

        __table = "account_bsdgroups"
        __group_nodes = self.__getChildNodes(__parent, "group")
        for __group_node in __group_nodes:
            __id_node = self.__getChildNode(__group_node, "id")
            if not __id_node: 
                continue

            __id = self.__getChildNodeValue(__id_node)
            if not __id:
                continue

            __name_node = self.__getChildNode(__group_node, "name")
            if not __name_node:
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __pairs = {}
            __pairs['bsdgrp_gid'] = __id
            __pairs['bsdgrp_group'] = __name

            self.__sql.insert(__table, __pairs)

        __table = "account_bsdusers"
        __user_nodes = self.__getChildNodes(__parent, "user")
        for __user_node in __user_nodes:
            __id_node = self.__getChildNode(__user_node, "id")
            if not __id_node:
                continue

            __id = self.__getChildNodeValue(__id_node)
            if not __id:
                continue

            __primarygroup_node = self.__getChildNode(__user_node, "primarygroup")
            if not __primarygroup_node:
                continue

            __primarygroup = self.__getChildNodeValue(__primarygroup_node)
            if not __primarygroup:
                continue

            __group_nodes = self.__getChildNodes(__user_node, "group")
            for __group_node in __group_nodes:
                __group = self.__getChildNodeValue(__group_node)

            __login_node = self.__getChildNode(__user_node, "login")
            if not __login_node:
                continue 

            __login = self.__getChildNodeValue(__login_node)
            if not __login:
                continue

            __fullname_node = self.__getChildNode(__user_node, "fullname")
            if not __fullname_node:
                continue

            __fullname = self.__getChildNodeValue(__fullname_node)
            if not __fullname:
                continue

            __password_node = self.__getChildNode(__user_node, "password")
            if not __password_node:
                continue

            __password = self.__getChildNodeValue(__password_node)
            if not __password:
                continue

            __shell_node = self.__getChildNode(__user_node, "shell")
            if not _shell_node:
                continue

            __shell = self.__getChildNodeValue(__shell_node)
            if not __shell:
                continue

            __pairs = {}
            __pairs['bsdusr_full_name'] = __fullname
            __pairs['bsdusr_username'] = __login
            #__pairs['bsdusr_group_id']
            __pairs['bsdusr_uid'] = __id
            #__pairs['bsdusr_unixhash']
            __pairs['bsdusr_shell'] = __shell
            #__pairs['bsdusr_builtin']
            __pairs['bsdusr_home'] = "/home/" + __login

            self.__sql.insert(__table, __pairs)


    def _handle_ad(self, __parent, __level):
        __nodemap = {'domaincontrollername':'ad_dcname', 'domainname_dns':'ad_domainname',
            'domainname_netbios':'ad_netbiosname', 'username':'ad_adminname',
            'password':'ad_adminpw', 'enable':None}

        __pairs = {}
        __table = "services_activedirectory"

        self.__set_pairs(__parent, __nodemap, __pairs)

        __regex = ".{1,120}"
        for __key in __pairs:
            if not re.match(__regex, __pairs[__key]):
                self.__fail("_handle_ad: %s is invalid", __pairs[__key])
                return

        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX Not sure I got this one right... XXX
    #
    def _handle_afp(self, __parent, __level):
        __nodemap = {'enable':None, 'afpname':'afp_srv_name', 'guest':'afp_srv_guest'}
        #__enable_node = self.__getChildNode(__parent, "enable")

        __pairs = {}
        __table = "services_afp"

        self.__set_pairs(__parent, __nodemap, __pairs)

        __regex = ".{1,120}"
        for __key in __pairs:
            if not re.match(__regex, __pairs[__key]):
                self.__fail("_handle_afp: %s is invalid", __pairs[__key])
                return

        if __pairs:
            self.__sql.insert(__table, __pairs) 

    #
    # XXX does this work? XXX
    #
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

            __regex = ".{1,120}"
            for __key in __pairs:
                if not re.match(__regex, __pairs[__key]):
                    self.__fail("_handle_cron: %s is invalid", __pairs[__key])
                    continue

            if __pairs:
                self.__sql.insert(__table, __pairs)

    #
    # XXX this needs more work XXX
    #
    #def _handle_disks(self, __parent, __level):
    #    __nodemap = {'name':'disk_name', 'devicespecialfile':'disk_disks',
    #        'harddiskstandby':'disk_hddstandby', 'acoustic':'disk_acousticlevel',
    #        'apm':None, 'transfermode':'disk_transfermode', 'type':None,
    #        'desc':'disk_description', 'size':None, 'smart':None, 'fstype':None}

    #    __disk_nodes = self.__getChildNodes(__parent, "disk")
    #    for __disk_node in __disk_nodes:

    #        __pairs = {}
    #        __table = "storage_disk"

    #        self.__set_pairs(__disk_node, __nodemap, __pairs)
    #        if __pairs:
    #            self.__sql.insert(__table, __pairs)

    #
    # XXX Is this correct ? XXX
    #
    def _handle_dynamicdns(self, __parent, __level):
        __nodemap = {'enable':None, 'provider':'ddns_provider',
            'domainname':'ddns_domain', 'username':'ddns_username',
            'password':'ddns_password', 'updateperiod':'ddns_updateperiod',
            'forcedupdateperiod':'ddns_fupdateperiod', 'wildcard':None, 'auxparam':None}

        __pairs = {} 
        __table = "services_dynamicdns"

        self.__set_pairs(__parent, __nodemap, __pairs)

        __regex = ".{1,120}"
        for __key in __pairs:
            if not re.match(__regex, __pairs[__key]):
                self.__fail("_handle_dynamicdns: %s is invalid", __pairs[__key])
                return

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

        __regex = ".{1,120}"
        for __key in __pairs:
            if not re.match(__regex, __pairs[__key]):
                self.__fail("_handle_dynamicdns: %s is invalid", __pairs[__key])
                return

        if __pairs:
            self.__sql.insert(__table, __pairs) 


    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gmirror(self, __parent, __level):
        __vdisks = self.__getChildNodes(__parent, "vdisk")
        for __vdisk in __vdisks:
            __name_node = self.__getChildNode(__vdisk, "name")
            if not __name_node: 
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __balance_node = self.__getChildNode(__vdisk, "balance")
            if not __balance_node:
                continue

            __balance = self.__getChildNodeValue(__balance_node)
            if not __balance:
                continue

            __type_node = self.__getChildNode(__vdisk, "type")
            if not __type_node:
                continue

            __type = self.__getChildNodeValue(__type_node)
            if not __type:
                continue

            __device_nodes = self.__getChildNode(__vdisk, "device")
            for __device_node in __device_nodes:
                __device_name = self.__getChildNodeValue(__device_node)

            __desc = None
            __desc_node = self.__getChildNode(__vdisk, "desc")
            if __desc_node:
                __desc = self.__getChildNodeValue(__desc_node)

            __devicespecialfile_node = self.__getChildNode(__vdisk, "devicespecialfile")
            if not __devicespecialfile_node: 
                continue

            __devicespecialfile = self.__getChildNodeValue(____devicespecialfile_node)
            if not __devicespecialfile: 
                continue



    #
    # XXX This needs to be looked at XXX
    #
    def _handle_gstripe(self, __parent, __level):
        __vdisks = self.__getChildNodes(__parent, "vdisk")
        for __vdisk in __vdisks:
            __name_node = self.__getChildNode(__vdisk, "name")
            if not __name_node: 
                continue

            __name = self.__getChildNodeValue(__name_node)
            if not __name:
                continue

            __balance_node = self.__getChildNode(__vdisk, "balance")
            if not __balance_node:
                continue

            __balance = self.__getChildNodeValue(__balance_node)
            if not __balance:
                continue

            __type_node = self.__getChildNode(__vdisk, "type")
            if not __type_node:
                continue

            __type = self.__getChildNodeValue(__type_node)
            if not __type:
                continue

            __device_nodes = self.__getChildNode(__vdisk, "device")
            for __device_node in __device_nodes:
                __device_name = self.__getChildNodeValue(__device_node)

            __desc = None
            __desc_node = self.__getChildNode(__vdisk, "desc")
            if __desc_node:
                __desc = self.__getChildNodeValue(__desc_node)

            __devicespecialfile_node = self.__getChildNode(__vdisk, "devicespecialfile")
            if not __devicespecialfile_node: 
                continue

            __devicespecialfile = self.__getChildNodeValue(____devicespecialfile_node)
            if not __devicespecialfile: 
                continue


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
    # XXX I'm not sure of the purpose of this one ... XXX
    #
    def _handle_iscsiinit(self, __parent, __level):
        pass


    def _handle_iscsitarget(self, __parent, __level):
        #
        # iSCSI tables:
        #
        # services_iscsitarget
        # X services_iscsitargetauthcredential
        # X services_iscsitargetauthorizedinitiator
        # X services_iscsitargetextent
        # X services_iscsitargetglobalconfiguration
        # X services_iscsitargetportal
        # services_iscsitargettoextent
        #


        #
        # Global Settings
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


        #
        # Device Extents
        #
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


        #
        # Portal Groups
        #
        __table = "services_iscsitargetportal"
        __portalgroup_nodemap = {'tag':'iscsi_target_portal_tag',
            'comment':'iscsi_target_portal_comment', 'portal':'iscsi_target_portal_listen' }
        __portalgroup_nodes = self.__getChildNodes(__parent, "portalgroup")
        for __portalgroup_node in __portalgroup_nodes:
            __pairs = {}

            self.__set_pairs(__portalgroup_node, __portalgroup_nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)

            
        #
        # Initiator Groups
        #
        __table = "services_iscsitargetauthorizedinitiator"
        __initialgroup_nodemap = {'tag':'iscsi_target_initiator_tag',
            'comment':'iscsi_target_initiator_comment',
            'iginitiatorname':'iscsi_target_initiator_initiators',
            'ignetmask':'iscsi_target_initiator_auth_network'}
        __initiatorgroup_nodes = self.__getChildNodes(__parent, "initiatorgroup")
        for __initiatorgroup_node in __initiatorgroup_nodes:
            __pais = {}

            self.__set_pairs(__initiatorgroup_node, __initiatorgroup_nodemap, __pairs)
            if __pairs:
                self.__sql.insert(__table, __pairs)



        #
        # Authentication
        #
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



        #__table = ""
        #__target_nodemap = {'name':'', 'alias':'', 'type':'', 'flags':'', 'comment':'',
        #    'authmethod':'', 'digest':'', 'queuedepth':'', 'inqvendor':'', 'inqproduct':'',
        #    'inqrevision':'', 'inqserial':'', 'pgigmap':'', 'agmap':'', 'lunmap':''}
        #__target_nodes = self.__getChildNodes(__parent, "target")
        #for __target_node in __target_nodes:
        #    pass


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

    def _handle_mounts(self, __parent, __level):
        __mount_nodes = self.__getChildNodes(__parent, "mount")
        for __mount_node in __mount_nodes:
            __type_node = self.__getChildNode(__mount_node, "type")
            if not __type_node:
                continue

            __type = self.__getChildNodeValue(__type_node) 
            if not __type:
                continue

            __desc = None
            __desc_node = self.__getChildNode(__mount_node, "desc")
            if __desc_node:
                __desc = self.__getChildNodeValue(__desc_node)

            __sharename_node = self.__getChildNode(__mount_node, "sharename")
            if not __sharename_node:
                continue

            __sharename = self.__getChildNodeValue(__sharename_node) 
            if not __sharename:
                continue

            __fstype_node = self.__getChildNode(__mount_node, "fstype")
            if not __fstype_node:
                continue

            __fstype = self.__getChildNodeValue(__fstype_node)
            if not __fstype:
                continue
             
            __mdisk_node = self.__getChildNode(__mount_node, "mdisk")
            if not __mdisk_node:
                continue

            __mdisk = self.__getChildNodeValue(__mdisk_node)
            if not __mdisk:
                continue

            __partition_node = self.__getChildNode(__mount_node, "partition")
            if not __partition_node:
                continue

            __partition = self.__getChildNodeValue(__partition_node)
            if not __partition:
                continue

            __devicespecialfile_node = self.__getChildNode(__mount_node, "devicespecialfile")
            if not __devicespecialfile_node:
                continue

            __devicespecialfile = self.__getChildNodeValue(__devicespecialfile)
            if not __devicespecialfile:
                continue

            __readonly = None
            __readonly_node = self.__getChildNode(__mount_node, "readonly")
            if __readonly_node:
                __readonly = self.__getChildNodeValue(__readonly_node)

            __fsck = None
            __fsck_node = self.__getChildNode(__mount_node, "fsck")
            if __fsck_node:
                __fsck = self.__getChildNodeValue(__fsck_node) 

            __owner = None
            __group = None
            __mode = None
            __accessrestrictions_node = self.__getChildNode(__mount_node, "accessrestrictions")
            if __accessrestrictions_node:
                __owner_node = self.__getChildNode(__accessrestrictions_node, "owner")
                if __owner_node:
                    __owner = self.__getChildNodeValue(__owner_node)

                __group_node = self.__getChildNode(__accessrestrictions_node, "group")
                if __group_node:
                    __group = self.__getChildNodeValue(__group_node)

                __mode_node = self.__getChildNode(__accessrestrictions_node, "mode")
                if __mode_node:
                    __mode = self.__getChildNodeValue(__mode_node)


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
    # XXX Not sure what do do with these on our system XXX
    #
    def _handle_rc(self, __parent, __level):
        __preinit_node = self.__getChildNode(__parent, "preinit")
        __cmd_nodes = self.__getChildNodes(__preinit_node, "cmd")
        for __cmd in __cmd_nodes:
            pass

        __postinit_node = self.__getChildNode(__parent, "postinit")
        __cmd_nodes = self.__getChildNodes(__postinit_node, "cmd")
        for __cmd in __cmd_nodes:
            pass

        __shutdown_node = self.__getChildNode(__parent, "shutdown")
        __cmd_nodes = self.__getChildNodes(__shutdown_node, "cmd")
        for __cmd in __cmd_nodes:
            pass


    def _handle_reboot(self, __parent, __level):
        self.__handle_cronjob(__parent, "root", "/sbin/reboot")

    #
    # XXX needs to be implemented XXX
    #
    def _handle_rsync(self, __parent, __level):
        __rsynclocal_node = self.__getChildNode(__parent, "rsynclocal")
        __rsyncclient_node = self.__getChildNode(__parent, "rsyncclient")

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


    def _handle_shutdown(self, __parent, __level):
        self.__handle_cronjob(__parent, "root", "/sbin/shutdown")


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
        rules = {}

        __rule_nodes = self.__getChildNodes(__parent, "rule")
        for __rule_node in __rule_nodes:
            __enable_node = self.__getChildNode(__rule_node, "enable")
            if not __enable_node:
                continue

            __ruleno_node = self.__getChildNode(__rule_node, "ruleno")
            if __ruleno_node:
                __ruleno = self.__getChildNodeValue(__ruleno_node)

            __action_node = self.__getChildNode(__rule_node, "action")
            if __action_node:
                __action = self.__getChildNodeValue(__action_node)

            __log_node = self.__getChildNode(__rule_node, "log")
            if __log_node:
                __log = self.__getChildNodeValue(__log_node)

            __protocol_node = self.__getChildNode(__rule_node, "protocol")
            if __protocol_node:
                __protocol = self.__getChildNodeValue(__protocol_node)

            __src_node = self.__getChildNode(__rule_node, "src")
            if __src_node:
                __src = self.__getChildNodeValue(__src_node)

            __srcport_node = self.__getChildNode(__rule_node, "srcport")
            if __srcport_node:
                __srcport = self.__getChildNodeValue(__srcport_node)

            __dst_node = self.__getChildNode(__rule_node, "dst")
            if __dst_node: 
                __dst = self.__getChildNodeValue(__dst_node)

            __dstport_node = self.__getChildNode(__rule_node, "dstport")
            if __dstport_node:
                __dstport = self.__getChildNodeValue(__dstport_node)

            __direction_node = self.__getChildNode(__rule_node, "direction")
            if __direction_node:
                __direction = self.__getChildNodeValue(__direction_node)

            __if_node = self.__getChildNode(__rule_node, "if")
            if __if_node:
                __if = self.__getChildNodeValue(__if_node)

            __extraoptions_node = self.__getChildNode(__rule_node, "extraoptions")
            if __extraoptions_node:
                __extraoptions = self.__getChildNodeValue(__extraoptions_node)

            __desc_node = self.__getChildNode(__rule_node, "desc")
            if __desc_node:
                __desc = self.__getChildNodeValue(__desc_node)

            __pf_rule = ""
            if __action == "allow": 
                __pf_rule = "pass "

            elif __action == "deny":
                __pf_rule = "block "

            if __direction == "in":
                __pf_rule += "in "
            
            elif __direction == "out":
                __pf_rule += "out "

            if __log:
                __pf_rule += "log "

            if __if:
                __pf_rule += "on %s " % (__if)

            if __protocol:
                if __protocol == "udp":
                    __pf_rule += "inet proto udp "

                elif __protocol == "tcp":
                    __pf_rule += "inet proto tcp "

                elif __protocol == "icmp":
                    __pf_rule += "proto icmp "

        #
        # XXX Get back to this XXX
        #


    def _handle_system_sysconsaver(self, __parent, __level):
        __sysconsaver_node = self.__getChildNode(__parent, "sysconsaver")
        if __sysconsaver_node:
            __enable_node = self.__getChildNode(__sysconsaver_node, "enable")
            if __enable_node:
                __table = "system_advanced"

                __pairs = {}
                __pairs['adv_consolescreensaver'] = 1
                self.__sql.do(__table, __pairs) 
                

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
        __allowfilecreateion_node = self.__getChildNode(__parent, "allowfilecreation")
        if __allowfilecreateion_node:
            __pairs['tftp_newfiles'] = 1

        if __pairs:
            self.__sql.insert(__table, __pairs) 

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

    def failed(self):
        return self.__failed


def make_db_backup(database, database_backup):
    pass

def restore_db(database_backup, database):
    pass


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
    debug = False
    config = None
    database = None
    backup = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "db:c:", ["debug", "config="])

    except:
        usage()

    if not len(opts):
        usage()

    for opt, arg in opts:
        if opt in ("-b", "--database"):
            database = arg
	  
        if opt in ("-c", "--config"):
            config = arg

        if opt in ("-d", "--debug"):
            debug = True

    if not config or not database:
        usage()


    backup = database + ".orig"
    make_db_backup(database, backup)

    cp = ConfigParser(config, database, debug)
    cp.run()

    if cp.failed():
        restore_db(backup, database)


if __name__ == '__main__':
    main()
