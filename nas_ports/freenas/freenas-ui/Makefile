# $FreeBSD$

PORTNAME=       freenas-ui
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS UI

USES=		python

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}django110>0:www/py-django110@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}lockfile>0:devel/py-lockfile@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}ipaddr>0:devel/py-ipaddr@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}sysctl>0:devel/py-sysctl@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}lxml>0:devel/py-lxml@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}dnspython>0:dns/py-dnspython@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}openssl>0:security/py-openssl@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}pycryptodome>0:security/py-pycryptodome@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}simplejson>0:devel/py-simplejson@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}sqlparse>0:databases/py-sqlparse@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}licenselib>0:freenas/py-licenselib@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}middlewared>0:freenas/py-middlewared@${PY_FLAVOR} \
	freenas-pkgtools>0:freenas/freenas-pkgtools \
	freenas-migrate93>0:freenas/freenas-migrate93 \
	${PYTHON_PKGNAMEPREFIX}libzfs>0:devel/py-libzfs@${PY_FLAVOR}

EXTRACT_ONLY=
WRKSRC=/usr/freenasUI

NO_BUILD=yes

MAKE_JOBS_UNSAFE=yes

ALL_TARGET=obj all

SUB_FILES=	pkg-install
SUB_LIST+=	PYTHON_CMD=${PYTHON_CMD}

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.pre.mk>

do-install:
	${PYTHON_CMD} -m compileall ${WRKSRC}/
	${ECHO_CMD} "@owner www"  >> ${TMPPLIST}
	${ECHO_CMD} "@group www"  >> ${TMPPLIST}
	${ECHO_CMD} "@comment files" >> ${TMPPLIST}
	${FIND} ${WRKSRC} -type f | \
		${SED} -e 's|^/usr/|/www/|' -e 's|^/||' \
		| ${SORT} >> ${TMPPLIST}
	${ECHO_CMD} www/freenasUI/local_settings.py >> ${TMPPLIST}
	${ECHO_CMD} "@comment directories" >> ${TMPPLIST}
	${FIND} ${WRKSRC} -type d \
		| ${SED} -e 's|^/usr/|/www/|' -e 's|^/||' -e 's|^|@dirrm |' \
		| ${SORT} -r >> ${TMPPLIST}

	${RM} -fr ${STAGEDIR}${PREFIX}/www/freenasUI
	${MKDIR} ${STAGEDIR}${PREFIX}/www/freenasUI
	${CP} -a ${WRKSRC}/ ${STAGEDIR}${PREFIX}/www/freenasUI
	${LN} -s -f /etc/local_settings.py ${STAGEDIR}${PREFIX}/www/freenasUI/local_settings.py

.include <bsd.port.post.mk>
