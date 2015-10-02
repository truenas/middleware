PROG=	verify_signature
SRCS=	verify_signature.c
LDADD=	-lssl -lcrypto
BINDIR=	${PREFIX}/libexec

WITHOUT_MAN=yes

beforeinstall:
	${INSTALL} -d ${DESTDIR}${BINDIR}

.include <bsd.prog.mk>
