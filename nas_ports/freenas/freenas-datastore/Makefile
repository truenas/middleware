#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-datastore
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS data store layer

USE_XZ=		yes
USE_PYTHON=	yes

OPTIONS_SINGLE=	USE_POSTGRESQL USE_MONGODB

.if ${PORT_OPTIONS:USE_POSTGRESQL}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}psycopg2:${PORTSDIR}/databases/py-psycopg2 \
		postgresql93-server:${PORTSDIR}/databases/postgresql93-server \
		postgresql93-contrib:${PORTSDIR}/databases/postgresql93-contrib \
		freenas-dispatcher:${PORTSDIR}/freenas/freenas-dispatcher
.endif

.if ${PORT_OPTIONS:USE_MONGODB}
RUN_DEPENDS=	pymongo:${PORTSDIR}/databases/pymongo \
		mongodb:${PORTSDIR}/databases/mongodb \
		freenas-dispatcher:${PORTSDIR}/freenas/freenas-dispatcher
.endif

EXTRACT_ONLY=

SUB_FILES=	pkg-install

NO_BUILD= 	yes
MAKE_JOBS_UNSAFE= yes
ALL_TARGET=	obj all
WRKSRC=		/usr/freenas_src/datastore

checksum fetch:
	echo ${.TARGET} not needed because building direct

do-install:
	${MAKE} -C ${WRKSRC} install PREFIX=${STAGEDIR}${PREFIX} PYTHON=${PYTHON_CMD}
	mkdir -p ${STAGEDIR}/data/freenas.db

.include <bsd.port.mk>
