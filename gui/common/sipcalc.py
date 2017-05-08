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
from freenasUI.common.pipesubr import pipeopen

SIPCALC_PATH = "/usr/local/bin/sipcalc"


class sipcalc_base_type(object):
    def __init__(self, *args, **kwargs):
        self.sipcalc = SIPCALC_PATH
        self.args = args
        self.iface = kwargs.get('iface', None)

        self.sipcalc_args = [self.sipcalc]
        for arg in args:
            self.sipcalc_args.append(str(arg))

        network = kwargs.get('network', None)
        if network:
            self.sipcalc_args.append(str(network))

        if self.iface:
            self.sipcalc_args.append(str(self.iface))

        # If we already have the results of the `sipcalc` shell call
        # then do not do a redudant second call
        # For more explanation see the __new__ method of the `sipcalc_type`
        # class.
        self.sipcalc_out = kwargs.get('sipcalc_out', None)
        if self.sipcalc_out is None:
            p1 = pipeopen(
                ' '.join(self.sipcalc_args),
                allowfork=True,
                important=False,
            )
            self.sipcalc_out = p1.communicate()
            if self.sipcalc_out:
                self.sipcalc_out = self.sipcalc_out[0]
                if self.sipcalc_out:
                    self.sipcalc_out = self.sipcalc_out.split('\n')

    def is_ipv4(self):
        res = False
        if self.sipcalc_out[0].startswith("-[ipv4") or (
            self.iface is not None and self.sipcalc_out[0].startswith("-[int-ipv4")
        ):
            res = True
        return res

    def is_ipv6(self):
        res = False
        if self.sipcalc_out[0].startswith("-[ipv6") or (
            self.iface is not None and self.sipcalc_out[0].startswith("-[int-ipv6")
        ):
            res = True
        return res

    def __str__(self):
        self_str = None
        if self.is_ipv4():
            self_str = "%s/%d" % (self.host_address, self.network_mask_bits)
        elif self.is_ipv6():
            self_str = "%s/%d" % (self.expanded_address, self.prefix_length)
        return self_str

    def __int__(self):
        return self.to_decimal()

    def __lt__(self, other):
        return self.to_decimal() < other

    def __le__(self, other):
        return self.to_decimal() <= other

    def __eq__(self, other):
        return self.to_decimal() == other

    def __ne__(self, other):
        return self.to_decimal() != other

    def __gt__(self, other):
        return self.to_decimal() > other

    def __ge__(self, other):
        return self.to_decimal() >= other

    def __add__(self, other):
        num = self.to_decimal() + other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __sub__(self, other):
        num = self.to_decimal() - other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __mul__(self, other):
        num = self.to_decimal() * other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __floordiv__(self, other):
        num = self.to_decimal() // other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __mod__(self, other):
        num = self.to_decimal() % other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __divmod__(self, other):
        num = (self.to_decimal() // other, self.to_decimal() % other)
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __pow__(self, other):
        num = self.to_decimal() ** other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __lshift__(self, other):
        num = self.to_decimal() << other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rshift__(self, other):
        num = self.to_decimal() >> other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __and__(self, other):
        num = self.to_decimal() & other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __xor__(self, other):
        num = self.to_decimal() ^ other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __or__(self, other):
        num = self.to_decimal() | other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __div__(self, other):
        return self.to_decimal() / other

    def __truediv__(self, other):
        return self.to_decimal() / other

    def __radd__(self, other):
        num = self.to_decimal() + other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rsub__(self, other):
        num = self.to_decimal() - other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rmul__(self, other):
        num = self.to_decimal() * other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rdiv__(self, other):
        num = self.to_decimal() / other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rtruediv__(self, other):
        num = self.to_decimal() // other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rfloordiv__(self, other):
        num = self.to_decimal() // other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rmod__(self, other):
        num = self.to_decimal() % other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rdivmod__(self, other):
        num = (self.to_decimal() // other, self.to_decimal() % other)
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rpow__(self, other):
        num = self.to_decimal() ** other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rlshift__(self, other):
        num = self.to_decimal() << other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rrshift__(self, other):
        num = self.to_decimal() << other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rand__(self, other):
        num = self.to_decimal() & other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __rxor__(self, other):
        num = self.to_decimal() ^ other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ror__(self, other):
        num = self.to_decimal() | other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __iadd__(self, other):
        num = self.to_decimal() + other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __isub__(self, other):
        num = self.to_decimal() - other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __imul__(self, other):
        num = self.to_decimal() * other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __idiv__(self, other):
        num = self.to_decimal() / other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __itruediv__(self, other):
        num = self.to_decimal() // other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ifloordiv__(self, other):
        num = self.to_decimal() // other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __imod__(self, other):
        num = self.to_decimal() % other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __invert__(self):
        num = ~self.to_decimal()
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ipow__(self, other):
        num = self.to_decimal() ** other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ilshift__(self, other):
        num = self.to_decimal() << other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __irshift__(self, other):
        num = self.to_decimal() >> other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __iand__(self, other):
        num = self.to_decimal() & other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ixor__(self, other):
        num = self.to_decimal() ^ other
        addr = self.to_ip(num)
        return sipcalc_type(addr)

    def __ior__(self, other):
        num = self.to_decimal() | other
        addr = self.to_ip(num)
        return sipcalc_type(addr)


class sipcalc_ipv4_type(sipcalc_base_type):
    def __init__(self, *args, **kwargs):
        super(sipcalc_ipv4_type, self).__init__(*args, **kwargs)

        for line in self.sipcalc_out:
            parts = line.split("-")

            i = 0
            plen = len(parts)
            while i < plen:
                parts[i] = parts[i].strip()
                i += 1

            if parts[0] == "Host address":
                self.host_address = parts[1]

            elif parts[0] == "Host address (decimal)":
                self.host_address_dec = int(parts[1])

            elif parts[0] == "Host address (hex)":
                self.host_address_hex = parts[1]

            elif parts[0] == "Network address":
                self.network_address = parts[1]

            elif parts[0] == "Network mask":
                self.network_mask = parts[1]

            elif parts[0] == "Network mask (bits)":
                self.network_mask_bits = int(parts[1])

            elif parts[0] == "Network mask (hex)":
                self.network_mask_hex = parts[1]

            elif parts[0] == "Broadcast address":
                self.broadcast_address = parts[1]

            elif parts[0] == "Cisco wildcard":
                self.cisco_wildcard = parts[1]

            elif parts[0] == "Addresses in network":
                self.network_addresses = int(parts[1])

            elif parts[0] == "Network range":
                self.network_range = parts[1:]

            elif parts[0] == "Usable range":
                self.usable_range = parts[1:]

    def to_decimal(self, addr=None):
        if addr is not None:
            num = sipcalc_type(addr).host_address_dec
        else:
            num = self.host_address_dec

        return num

    def to_ip(self, num=None):
        if num is None:
            num = self.host_address_dec

        oct1 = (num >> 24) & 0xff
        oct2 = (num >> 16) & 0xff
        oct3 = (num >> 8) & 0xff
        oct4 = (num >> 0) & 0xff

        addr = "%d.%d.%d.%d/%d" % (oct1, oct2, oct3, oct4, self.network_mask_bits)
        return addr

    def in_network(self, addr):
        res = False

        st_addr = sipcalc_type(addr).host_address_dec
        st_start = sipcalc_type("%s/%d" % (
            self.network_range[0],
            self.network_mask_bits
        )).host_address_dec
        st_end = sipcalc_type("%s/%d" % (
            self.network_range[1],
            self.network_mask_bits
        )).host_address_dec

        if st_addr >= st_start and st_addr <= st_end:
            res = True

        return res

    def get_next_addr(self, addr=None):
        naddr = ""

        if addr is not None:
            addr = sipcalc_type(addr).host_address_dec
        else:
            addr = self.host_address_dec

        addr += 1

        oct1 = (addr >> 24) & 0xff
        oct2 = (addr >> 16) & 0xff
        oct3 = (addr >> 8) & 0xff
        oct4 = (addr >> 0) & 0xff

        naddr = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
        return naddr


class sipcalc_ipv6_type(sipcalc_base_type):
    def __init__(self, *args, **kwargs):
        super(sipcalc_ipv6_type, self).__init__(*args, **kwargs)

        network_range = 0
        for line in self.sipcalc_out:
            parts = line.split("-")

            i = 0
            plen = len(parts)
            while i < plen:
                parts[i] = parts[i].strip()
                i += 1

            if parts[0] == "Expanded Address":
                self.expanded_address = parts[1]

            elif parts[0] == "Compressed address":
                self.compressed_address = parts[1]

            elif parts[0] == "Subnet prefix (masked)":
                self.subnet_prefix_masked = parts[1]

            elif parts[0] == "Address ID (masked)":
                self.address_id_masked = parts[1]

            elif parts[0] == "Prefix address":
                self.prefix_address = parts[1]

            elif parts[0] == "Prefix length":
                self.prefix_length = int(parts[1])

            elif parts[0] == "Address type":
                self.address_type = parts[1]

            elif parts[0] == "Network range":
                self.network_range = [None, None]
                self.network_range[0] = parts[1]
                network_range = 1

            elif network_range == 1:
                network_range = 0
                self.network_range[1] = parts[0]

    def to_binary(self, addr=None):
        numbers = {
            '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
            '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'a': 10,
            'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15
        }

        if addr is not None:
            addr = sipcalc_type(addr).expanded_address
        else:
            addr = self.expanded_address

        bnum = ""
        octets = addr.split(':')
        for oct in octets:

            # hex to decimal
            dnum = 0
            for b in oct:
                b = b.lower()
                dnum *= 16
                dnum += numbers[b]

            # decimal to binary
            tbnum = ""
            while True:
                if dnum & 1:
                    tbnum = "1%s" % tbnum
                else:
                    tbnum = "0%s" % tbnum

                dnum = int(dnum / 2)
                if dnum < 1:
                    break

            tbnum = tbnum.zfill(16)
            bnum = "%s%s" % (bnum, tbnum)

        return bnum

    def to_decimal(self, addr=None):
        numbers = {
            '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
            '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'a': 10,
            'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15
        }
        if addr is not None:
            addr = sipcalc_type(addr).expanded_address
        else:
            addr = self.expanded_address

        si = 128
        num = 0
        octets = addr.split(':')
        for oct in octets:
            si -= 16

            # hex to decimal
            dnum = 0
            for b in oct:
                b = b.lower()
                dnum *= 16
                dnum += numbers[b]

            num += dnum << si

        return num

    def to_ip(self, num=None):
        if num is None:
            num = self.to_decimal()

        addr = ""
        haddr = hex(num)
        parts1 = haddr.split('x')
        if len(parts1) > 1:
            parts2 = parts1[1].split('L')
            hstr = parts2[0]

            i = 0
            hlen = len(hstr)
            while i < hlen:
                addr += hstr[i]
                if (i + 1) % 4 == 0 and (i + 1) < hlen:
                    addr += ':'
                i += 1

        addr = "%s/%d" % (addr, self.prefix_length)
        return addr

    def in_network(self, addr):
        res = False

        st_addr = sipcalc_type(addr)
        st_start = sipcalc_type(self.network_range[0])

        st_baddr = self.to_binary(st_addr.expanded_address)
        st_bstart = self.to_binary(st_start.expanded_address)

        if st_baddr[0:self.prefix_length] == st_bstart[0:self.prefix_length]:
            res = True

        return res

    def get_next_addr(self, addr=None):
        naddr = ""

        if addr is not None:
            addr = sipcalc_type(addr).expanded_address
        else:
            addr = self.expanded_address

        daddr = self.to_decimal(addr)
        daddr += 1

        haddr = hex(daddr)
        parts1 = haddr.split('x')
        if len(parts1) > 1:
            parts2 = parts1[1].split('L')
            hstr = parts2[0]

            i = 0
            hlen = len(hstr)
            while i < hlen:
                naddr += hstr[i]
                if (i + 1) % 4 == 0 and (i + 1) < hlen:
                    naddr += ':'
                i += 1

        if not naddr:
            naddr = None

        return naddr


class sipcalc_type(sipcalc_base_type):
    def __new__(cls, *args, **kwargs):
        obj = None
        sbt = sipcalc_base_type(*args, **kwargs)

        # Note: `sipcalc_out` is the stdout result of the subprocess that calls
        # the commandline sipcalc. Now the classes `sipcalc_ipv4_type` as well as
        # `sipcalc_ipv6_type` both subclass `sipcalc_base_type` whose __init__ method
        # is actually where the subprocess call is made. Since we need to make said call
        # before figuring out if its ipv4 or ipv6 we alread have obtained the subprocess
        # output in that call and the `sipcalc_out` kwargs to the respective inherited classes
        # prevents another redundant subprocess call from being made
        # I hope this explanation is good enough.
        if sbt.is_ipv4():
            kwargs['sipcalc_out'] = sbt.sipcalc_out
            obj = sipcalc_ipv4_type(*args, **kwargs)

        elif sbt.is_ipv6():
            kwargs['sipcalc_out'] = sbt.sipcalc_out
            obj = sipcalc_ipv6_type(*args, **kwargs)

        return obj
