PREFIX ?= /usr/local
PYTHON ?= python

install:
	install tools/etcd ${PREFIX}/sbin/
	install -d ${PREFIX}/lib/etcd
	install -d ${PREFIX}/lib/etcd/src
	install -d ${PREFIX}/lib/etcd/plugins
	cp -a src/ ${PREFIX}/lib/etcd/src/
	cp -a plugins/ ${PREFIX}/lib/etcd/plugins/