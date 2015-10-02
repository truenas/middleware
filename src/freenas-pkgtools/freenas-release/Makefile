.include <bsd.own.mk>

MK_MAN= no

SCRIPTS=	freenas-release.py

FILESDIR=	/usr/local/etc
FILES=	freenas-release-default.conf
FILESOWN=	root
FILESGRP=	wheel
FILESMODE=	0644

beforeinstall:
	${INSTALL} -d ${DESTDIR}${FILESDIR}

.include <bsd.prog.mk>
