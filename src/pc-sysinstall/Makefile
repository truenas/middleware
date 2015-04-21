# $FreeBSD: src/usr.sbin/pc-sysinstall/Makefile,v 1.1 2010/06/24 22:21:47 imp Exp $
SUBDIR=backend backend-partmanager backend-query conf doc examples
SUBDIR+=pc-sysinstall

beforeinstall: 
.for i in backend backend-partmanager backend-query conf conf/license doc 
	mkdir -p ${DESTDIR}/usr/share/pc-sysinstall/$i 
.endfor 
	mkdir -p ${DESTDIR}/usr/sbin 
	mkdir -p ${DESTDIR}/usr/share/examples/pc-sysinstall
	mkdir -p ${DESTDIR}/usr/share/man/man8

.include <bsd.subdir.mk>
