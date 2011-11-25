#+
# Copyright 2011 iXsystems, Inc.
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
from freenasUI.common.acl import *
from freenasUI.common.freenasnfsv4 import *
from freenasUI.common.freenasufs import *

class ACL(Base_ACL):
    def __new__(cls, path, type = None):

        obj = None
        if Base_ACL.get_acl_type(path) == ACL_FLAGS_TYPE_NFSV4:
            obj = NFSv4_ACL(path)
        else:
            obj = POSIX_ACL(path)

        return obj


class ACL_Hierarchy(Base_ACL_Hierarchy):
    def __new__(cls, path):

        obj = None
        if Base_ACL.get_acl_type(path) == ACL_FLAGS_TYPE_NFSV4:
            obj = NFSv4_ACL_Hierarchy(path)
        else:
            obj = POSIX_ACL_Hierarchy(path)

        return obj
