PREFIX ?= /usr/local
PYTHON ?= python

install:
	install etc/dispatcher ${PREFIX}/etc/rc.d/
	install etc/middleware.conf ${PREFIX}/etc/middleware.conf
	install tools/dispatcherd ${PREFIX}/sbin/
	install tools/dispatcherctl ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/dispatcher/src
	install -d ${PREFIX}/lib/dispatcher/plugins
	install -d ${PREFIX}/libexec/dispatcher
	cp -R src/ ${PREFIX}/lib/dispatcher/src/
	cp -R plugins/ ${PREFIX}/lib/dispatcher/plugins/
	cp -R libexec/ ${PREFIX}/libexec/dispatcher/
	cd client/python && ${PYTHON} setup.py install --prefix=${PREFIX}
