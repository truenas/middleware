# Copyright 2013 iXsystems, Inc.
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
import logging

log = logging.getLogger('common.cmd')


class cmd_arg(object):
    def __init__(self, int, string, arg=False, argname=None):
        self.int = int
        self.string = string
        self.arg = arg
        self.argname = argname

    def __str__(self):
        return self.string

    def __lt__(self, other):
        return self.int < other

    def __le__(self, other):
        return self.int <= other

    def __eq__(self, other):
        return self.int == other

    def __ne__(self, other):
        return self.int != other

    def __gt__(self, other):
        return self.int > other

    def __ge__(self, other):
        return self.int >= other

    def __add__(self, other):
        return self.int + other

    def __sub__(self, other):
        return self.int - other

    def __mul__(self, other):
        return self.int * other

    def __floordiv__(self, other):
        return self.int // other

    def __mod__(self, other):
        return self.int % other

    def __divmod__(self, other):
        return (self.int // other, self.int % other)

    def __pow__(self, other):
        return self.int ** other

    def __lshift__(self, other):
        return self.int << other

    def __rshift__(self, other):
        return self.int >> other

    def __and__(self, other):
        return self.int & other

    def __xor__(self, other):
        return self.int ^ other

    def __or__(self, other):
        return self.int | other

    def __div__(self, other):
        return self.int / other

    def __truediv__(self, other):
        return self.int / other

    def __radd__(self, other):
        return self.int + other

    def __rsub__(self, other):
        return self.int - other

    def __rmul__(self, other):
        return self.int * other

    def __rdiv__(self, other):
        return self.int / other

    def __rtruediv__(self, other):
        return self.int // other

    def __rfloordiv__(self, other):
        return self.int // other

    def __rmod__(self, other):
        return self.int % other

    def __rdivmod__(self, other):
        return (self.int // other, self.int % other)

    def __rpow__(self, other):
        return self.int ** other

    def __rlshift__(self, other):
        return self.int << other

    def __rrshift__(self, other):
        return self.int << other

    def __rand__(self, other):
        return self.int & other

    def __rxor__(self, other):
        return self.int ^ other

    def __ror__(self, other):
        return self.int | other

    def __iadd__(self, other):
        return self.int + other

    def __isub__(self, other):
        return self.int - other

    def __imul__(self, other):
        return self.int * other

    def __idiv__(self, other):
        return self.int / other

    def __itruediv__(self, other):
        return self.int // other

    def __ifloordiv__(self, other):
        return self.int // other

    def __imod__(self, other):
        return self.int % other

    def __invert__(self):
        return ~self.int

    def __ipow__(self, other):
        return self.int ** other

    def __ilshift__(self, other):
        return self.int << other

    def __irshift__(self, other):
        return self.int >> other

    def __iand__(self, other):
        return self.int & other

    def __ixor__(self, other):
        return self.int ^ other

    def __ior__(self, other):
        return self.int | other


class cmd_pipe(object):
    def __init__(self, cmd, func=None, **kwargs):
        log.debug("cmd_pipe.__init__: cmd = %s, kwargs = %s", cmd, kwargs)

        from freenasUI.common.pipesubr import pipeopen

        self.error = None
        self.__pipe = pipeopen(cmd, allowfork=False, important=True, close_fds=True, **(kwargs.get('pipeopen_kwargs', None) or {}))

        self.__stdin = self.__pipe.stdin
        self.__stdout = self.__pipe.stdout
        self.__stderr = self.__pipe.stderr

        self.__out, self.err = self.__pipe.communicate()

        if func is not None:
            for line in self.__out.splitlines():
                line = line.strip()
                func(line, **kwargs)

        for line in self.__out.splitlines():
            log.debug("cmd_pipe.__init__: out = %s", line)
        for line in self.err.splitlines():
            log.debug("cmd_pipe.__init__: err = %s", line)

        if self.__pipe.returncode != 0:
            self.error = 'The command %s failed: "%s"' % (
                cmd,
                self.err or self.__out,
            )

        self.returncode = self.__pipe.returncode
        log.debug("cmd_pipe.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line
