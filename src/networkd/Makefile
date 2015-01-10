PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/networkd ${PREFIX}/etc/rc.d/
	install sbin/networkd ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/networkd
	install -d ${PREFIX}/lib/networkd/src
	cp -a src/ ${PREFIX}/lib/networkd/src/