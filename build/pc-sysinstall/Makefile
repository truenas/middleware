# $FreeBSD: head/usr.sbin/pc-sysinstall/Makefile 209513 2010-06-24 22:21:47Z imp $
SUBDIR=backend backend-partmanager backend-query conf doc
SUBDIR+=pc-sysinstall

beforeinstall:
.for i in backend backend-partmanager backend-query conf conf/license doc
	mkdir -p ${DESTDIR}/usr/share/pc-sysinstall/$i
.endfor
	mkdir -p ${DESTDIR}/usr/sbin

.include <bsd.subdir.mk>
