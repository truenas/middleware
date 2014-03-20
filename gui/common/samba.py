#+
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
SAMBA_TOOL = "/usr/local/bin/samba-tool"

class SambaConf(object):
    # Stub! Implement later!
    pass

class Samba4(object):
    def __init__(self, *args, **kwargs):
        self.samba_tool_path = SAMBA_TOOL
        self.provisioned_file = SAMBA_PROVISIONED_FILE

    def samba_tool(self, cmd, args, nonargs=None, quiet=False):
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
        if out and out[1]:
            for line in out[1].split('\n'):
                print line
  
        if p.returncode != 0:
            return False

        return True

    def domain_provisioned(self):
        return self.sentinel_file_exists()

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

        return self.samba_tool("domain provision", args)

    def disable_password_complexity(self):
        return self.samba_tool("domain passwordsettings set", { 'complexity': 'off'})

    def set_administrator_password(self):
        try:
            dc = DomainController.objects.all()[0]
        except:
            pass

        return self.set_user_password('Administrator', dc.dc_passwd)

    def change_forest_level(self, level):
        return self.samba_tool("domain level raise", { 'forest-level': level})

    def change_domain_level(self, level):
        return self.samba_tool("domain level raise", { 'domain-level': level})

    def set_user_password(self, user, password):
        return self.samba_tool("user setpassword", {'newpassword': password }, [user], True)

    def sentinel_file_exists(self):
        return (os.path.exists(self.provisioned_file) and \
            os.path.isfile(self.provisioned_file))

    def sentinel_file_create(self):
        ret = False
        try:
            with open(self.provisioned_file, 'w') as f:
                f.close()
            os.chmod(self.provisioned_file, 0400)
            ret = True

        except Exception as e:
            print >> sys.stderr, "Unable to create %s: %s" % (self.provisioned_file, e)
            ret = False

        return ret

    def sentinel_file_remove(self):
        ret = True

        if os.path.exists(self.provisioned_file):
            try:
                os.unlink(self.provisioned_file)
                ret = True  

            except Exception as e:
                print >> sys.stderr, "Unable to remove %s: %s" % (self.provisioned_file, e)
                ret = False

        return ret

