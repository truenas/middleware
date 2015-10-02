.include <bsd.own.mk>

FILESDIR= ${PREFIX}/share/certs

FILES=	freenas-update.pem \
	iX-CA.pem

beforeinstall:
	${INSTALL} -d ${DESTDIR}${FILESDIR}

.include <bsd.lib.mk>

