# The iX autotuning package.
#
# Garrett Cooper, December 2011
#
# iXsystems, Inc. proprietary. Do not redistribute.

PORTNAME=	autotune
PORTVERSION=	0.2.0
CATEGORIES=	misc

MASTER_SITES=
DISTFILES=	

MAINTAINER=	truenas@ixsystems.com
COMMENT=	TrueNAS performance autotuning utility

# Required by .
USE_GMAKE=	yes
# Definitely required though.
USE_PYTHON=	yes

NO_MTREE=	yes
NO_WRKSUBDIR=	yes

.include <bsd.port.pre.mk>

PLIST_FILES=	tools/autotune

PREFIX=		${LOCALBASE}/www/freenasUI

do-extract:
	${MKDIR} ${WRKSRC}
	${CP} ${FILESDIR}/autotune.py ${WRKSRC}/.

do-build:
	cd ${WRKSRC} && ${SETENV} ${MAKE_ENV} \
	    ${PYTHON_CMD} \
	    ${PYTHONBASE}/share/${PYTHON_DEFAULT_VERSION}/Tools/freeze/freeze.py \
	    -X pdb -X pydoc -X unittest autotune.py
	cd ${WRKSRC} && ${GMAKE} all

do-install:
	${MKDIR} ${DESTDIR}/${PREFIX}/tools
	cd ${WRKSRC} && ${INSTALL_SCRIPT} autotune ${DESTDIR}/${PREFIX}/tools/.

.include <bsd.port.post.mk>
