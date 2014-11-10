PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/etcfs ${PREFIX}/etc/rc.d/
	install tools/mount_etcfs ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/etcfs
	install -d ${PREFIX}/lib/etcfs/src
	install -d ${PREFIX}/lib/etcfs/plugins
	cp -a src/ ${PREFIX}/lib/etcfs/src/
	cp -a plugins/ ${PREFIX}/lib/etcfs/plugins/