PREFIX ?= /usr/local
PYTHON ?= python

install:
	install -d ${PREFIX}/lib/datastore
	install -d ${PREFIX}/lib/datastore/drivers
	install -d ${PREFIX}/share/datastore
	install tools/dsutil ${PREFIX}/sbin/
	install tools/dsdump ${PREFIX}/sbin/
	install tools/dsrestore ${PREFIX}/sbin/
	install tools/dsmigrate ${PREFIX}/sbin/
	install tools/dspasswd ${PREFIX}/sbin/
	install tools/dsinit ${PREFIX}/sbin/
	install etc/datastore ${PREFIX}/etc/rc.d/
	install share/factory.json ${PREFIX}/share/datastore/
	cp -R drivers/ ${PREFIX}/lib/datastore/drivers/
	${PYTHON} setup.py install --prefix=${PREFIX}
