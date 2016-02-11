import os, sys
import dns.resolver
from dns.rdatatype import ANY as rANY, NS as rNS

from system.ixselftests import TestObject

RESOLV_CONF = "/etc/resolv.conf"

def List():
	return ["resolv_conf", "resolver"]

class resolv_conf(TestObject):
	def __init__(self, handler=None):
                super(self.__class__, self).__init__(handler)
                self._name = "resolv.conf"

	def Enabled(self):
		return True

	def Test(self):
		if os.path.exists(RESOLV_CONF):
			return self._handler.Pass(self._name, "exists")
		else:
			return self._handler.Fail(self._name, "does not exist")

class resolver(TestObject):
	def __init__(self, handler=None):
                super(self.__class__, self).__init__(handler)
                self._name = "resolver"
                
	def Enabled(self):
		return True

	def Test(self):
		# Do a simple query
		servers = []
		with open(RESOLV_CONF) as f:
			for line in f:
				line = line.rstrip()
				if line.startswith("#"):
					continue
				if "nameserver" in line:
					elements = line.split()
					# First element should be "nameserver"
					for srv in elements[1:]:
						if "," in srv:
							for srv2 in srv.split(","):
								servers.append(srv2.strip().rstrip())
						else:
							servers.append(srv.strip().rstrip())
		my_resolver = dns.resolver.Resolver()
                # Set a timeout of 1 second.
                my_resolver.timeout = 1.0
                # Should I loop over them instead?
		my_resolver.nameservers = servers
		try:
			answer = my_resolver.query(".", rdtype=rNS)
			if not answer:
				raise Exception("bah")
                        return self._handler.Pass("resolver")
		except:
			return self._handler.Fail("resolver", "Cannot query resolver")

