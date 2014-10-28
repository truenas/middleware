PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/dispatcher ${PREFIX}/etc/rc.d/
	install etc/middleware.conf ${PREFIX}/etc/middleware.conf
	install tools/dispatcherd ${PREFIX}/sbin/
	install tools/dispatcherctl ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/dispatcher/src
	install -d ${PREFIX}/lib/dispatcher/plugins
	cp -R src/ ${PREFIX}/lib/dispatcher/src/
	cp -R plugins/ ${PREFIX}/lib/dispatcher/plugins/
	cd client/python && ${PYTHON} setup.py install --prefix=${PREFIX}
