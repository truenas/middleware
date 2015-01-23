PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/statd ${PREFIX}/etc/rc.d/
	install sbin/statd ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/statd
	install -d ${PREFIX}/lib/statd/src
	install -d ${PREFIX}/lib/statd/plugins
	cp -a plugins/ ${PREFIX}/lib/statd/plugins/
	cp -a src/ ${PREFIX}/lib/statd/src/