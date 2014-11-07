PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/etcfs ${PREFIX}/etc/rc.d/
	install etc/mount_etcfs ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/etcfs
	cp -R src/ ${PREFIX}/lib/etcfs/
