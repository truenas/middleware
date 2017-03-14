# Copyright 2014 iXsystems, Inc.
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
import os
import sys

from freenasUI.common.pipesubr import pipeopen
from freenasUI.services.models import DomainController

SAMBA_DB_PATH = "/var/db/samba4"
SAMBA_PROVISIONED_FILE = os.path.join(SAMBA_DB_PATH, ".provisioned")
SAMBA_USER_IMPORT_FILE = os.path.join(SAMBA_DB_PATH, ".usersimported")
SAMBA_TOOL = "/usr/local/bin/samba-tool"


class SambaConf(object):
    # Stub! Implement later!
    pass


class Samba4(object):
    def __init__(self, *args, **kwargs):
        self.samba_tool_path = SAMBA_TOOL

    def samba_tool(self, cmd, args, nonargs=None, quiet=False, buf=None):
        samba_tool_args = cmd

        if args:
            for key in args:
                if args[key]:
                    samba_tool_args = "%s --%s '%s'" % (samba_tool_args, key, args[key])
                else:
                    samba_tool_args = "%s --%s" % (samba_tool_args, key)

        if nonargs:
            for key in nonargs:
                samba_tool_args = "%s '%s'" % (samba_tool_args, key)

        p = pipeopen("%s %s" % (self.samba_tool_path, samba_tool_args), quiet=quiet)
        out = p.communicate()
        if buf is not None:
            buf.append(out)

        if p.returncode != 0:
            return False

        return True

    def domain_provisioned(self):
        return self.sentinel_file_exists(SAMBA_PROVISIONED_FILE)

    def domain_sentinel_file_create(self):
        return self.sentinel_file_create(SAMBA_PROVISIONED_FILE)

    def domain_sentinel_file_remove(self):
        return self.sentinel_file_remove(SAMBA_PROVISIONED_FILE)

    def domain_provision(self):
        try:
            dc = DomainController.objects.all()[0]
        except:
            pass

        args = {
            'realm': dc.dc_realm,
            'domain': dc.dc_domain,
            'dns-backend': dc.dc_dns_backend,
            'server-role': dc.dc_role,
            'function-level': dc.dc_forest_level,
            'use-ntvfs': None,
            'use-rfc2307': None
        }

        buf = []
        res = self.samba_tool("domain provision", args, buf=buf)
        try:
            buf = buf[0][1]
            for line in buf.splitlines():
                print("%s" % line, file=sys.stdout)

        except:
            pass

        return res

    def disable_password_complexity(self):
        return self.samba_tool("domain passwordsettings set", {'complexity': 'off'})

    def set_min_pwd_length(self):
        return self.samba_tool("domain passwordsettings set", {'min-pwd-length': '1'})

    def set_administrator_password(self):
        try:
            dc = DomainController.objects.all()[0]
        except:
            pass

        return self.set_user_password('Administrator', dc.dc_passwd)

    def change_forest_level(self, level):
        return self.samba_tool("domain level raise", {'forest-level': level})

    def change_domain_level(self, level):
        return self.samba_tool("domain level raise", {'domain-level': level})

    def user_add(self):
        pass

    def user_create(self):
        pass

    def user_delete(self, user):
        return self.samba_tool("user delete", None, [user])

    def user_disable(self, user):
        return self.samba_tool("user disable", None, [user])

    def user_enable(self, user):
        return self.samba_tool("user enable", None, [user])

    def user_list(self):
        buf = []
        users = []

        if not self.samba_tool("user list", None, buf=buf):
            return users

        try:
            buf = buf[0][0]
            users = buf.splitlines()

        except:
            pass

        return users

    def user_password(self):
        pass

    def user_setexpiry(self):
        pass

    def user_setpassword(self):
        pass

    def set_user_password(self, user, password):
        return self.samba_tool("user setpassword", {'newpassword': password}, [user], True)

    def group_add(self, group):
        return self.samba_tool("group add", None, [group])

    def group_create(self, group):
        return self.samba_tool("group create", None, [group])

    def group_addmembers(self, group, members):
        return self.samba_tool(
            "group addmembers", None, [group, ','.join(members)]
        )

    def group_delete(self, group):
        return self.samba_tool("group delete", None, [group])

    def group_list(self):
        buf = []
        groups = []

        if not self.samba_tool("group list", None, buf=buf):
            return groups

        try:
            buf = buf[0][0]
            groups = buf.splitlines()

        except:
            pass

        return groups

    def group_listmembers(self, group):
        buf = []
        members = []

        if not self.samba_tool("group listmembers", None, [group], buf=buf):
            return members

        try:
            buf = buf[0][0]
            members = buf.splitlines()

        except:
            pass

        return members

    def group_removemembers(self, group, members):
        return self.samba_tool(
            "group removemembers", None, [group, ','.join(members)]
        )

    def sentinel_file_exists(self, sentinel_file):
        return (
            os.path.exists(sentinel_file) and os.path.isfile(sentinel_file)
        )

    def sentinel_file_create(self, sentinel_file):
        ret = False
        try:
            with open(sentinel_file, 'w') as f:
                f.close()
            os.chmod(sentinel_file, 0o400)
            ret = True

        except Exception as e:
            print("Unable to create %s: %s" % (sentinel_file, e), file=sys.stderr)
            ret = False

        return ret

    def sentinel_file_remove(self, sentinel_file):
        ret = True

        if os.path.exists(sentinel_file):
            try:
                os.unlink(sentinel_file)
                ret = True

            except Exception as e:
                print("Unable to remove %s: %s" % (sentinel_file, e), file=sys.stderr)
                ret = False

        return ret

    def users_imported(self):
        return self.sentinel_file_exists(SAMBA_USER_IMPORT_FILE)

    def user_import_sentinel_file_create(self):
        return self.sentinel_file_create(SAMBA_USER_IMPORT_FILE)

    def user_import_sentinel_file_remove(self):
        return self.sentinel_file_remove(SAMBA_USER_IMPORT_FILE)
