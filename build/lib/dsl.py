#+
# Copyright 2015 iXsystems, Inc.
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
import uuid


class GlobalsWrapper(dict):
    def __init__(self, env):
        super(GlobalsWrapper, self).__init__()
        self.dict = {}
        self.env = env

    def __getitem__(self, item):
        if item.isupper():
            return self.env.get(item, None)

        if item == 'e':
            from utils import e
            return e

        if item == 'include':
            return self.include

        return self.wrap(item)

    def __setitem__(self, key, value):
        self.dict[key] = value

    def wrap(self, name):
        def fn(*args, **kwargs):
            if args:
                if name not in self.dict:
                    self.dict[name] = []
                self.dict[name].extend(args)

            if kwargs:
                if name not in self.dict:
                    self.dict[name] = {}
                ident = kwargs.get('name', str(uuid.uuid4()))
                self.dict[name][ident] = kwargs

        return fn

    def include(self, filename):
        d = load_file(filename, self.env)
        for k, v in d.items():
            if k in self.dict:
                if isinstance(self.dict[k], dict):
                    self.dict[k].update(v)
                elif isinstance(self.dict[k], list):
                    self.dict[k] += v
            else:
                self.dict[k] = v



def load_file(filename, env):
    g = GlobalsWrapper(env)
    execfile(os.path.expandvars(filename), g)
    return g.dict