# afpusers, a replacement for macusers
#
PORTNAME=	afpusers
PORTVERSION=	0.1
CATEGORIES=	net

MASTER_SITES=
DISTFILES=	

MAINTAINER=	truenas@ixsystems.com
COMMENT=	AFP Users utility

# Definitely required though.
USE_PYTHON=	yes

NO_MTREE=	yes
NO_WRKSUBDIR=	yes

.include <bsd.port.pre.mk>

PLIST_FILES=	net/afpusers

PREFIX=		${LOCALBASE}/bin

do-extract:
	${MKDIR} ${WRKSRC}
	${CP} ${FILESDIR}/afpusers.py ${WRKSRC}/.

do-build:
	cd ${WRKSRC} && ${SETENV} ${MAKE_ENV} \
	    ${PYTHON_CMD} \
	    ${PYTHONBASE}/share/${PYTHON_DEFAULT_VERSION}/Tools/freeze/freeze.py \
	    -X pdb -X pydoc -X unittest afpusers.py
	cd ${WRKSRC} && ${MAKE} all

do-install:
	${MKDIR} ${DESTDIR}/${PREFIX}/bin
	cd ${WRKSRC} && ${INSTALL_SCRIPT} afpusers ${DESTDIR}/${PREFIX}/bin/.

.include <bsd.port.post.mk>
