PREFIX ?= /usr/local
PYTHON ?= python

install:
	install sbin/fnstatd ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/fnstatd
	install -d ${PREFIX}/lib/fnstatd/src
	install -d ${PREFIX}/lib/fnstatd/plugins
	#cp -a plugins/ ${PREFIX}/lib/fnstatd/plugins/
	cp -a src/ ${PREFIX}/lib/fnstatd/src/
