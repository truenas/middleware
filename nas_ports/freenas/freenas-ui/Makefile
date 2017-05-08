# $FreeBSD$

PORTNAME=       freenas-ui
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS UI

PRODUCT?=
USES=		python

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}django110>0:www/py-django110 \
	uwsgi>0:www/uwsgi \
	${PYTHON_PKGNAMEPREFIX}django-formtools>0:www/py-django-formtools \
	${PYTHON_PKGNAMEPREFIX}django-tastypie>0:www/py-django-tastypie \
	${PYTHON_PKGNAMEPREFIX}lockfile>0:devel/py-lockfile \
	${PYTHON_PKGNAMEPREFIX}ipaddr>0:devel/py-ipaddr \
	${PYTHON_PKGNAMEPREFIX}bsddb3>0:databases/py-bsddb3 \
	${PYTHON_PKGNAMEPREFIX}polib>0:devel/py-polib \
	${PYTHON_PKGNAMEPREFIX}pyldap>0:net/py-pyldap \
	${PYTHON_PKGNAMEPREFIX}dojango>0:www/py-dojango \
	${PYTHON_PKGNAMEPREFIX}sysctl>0:devel/py-sysctl \
	${PYTHON_PKGNAMEPREFIX}lxml>0:devel/py-lxml \
	${PYTHON_PKGNAMEPREFIX}pybonjour>0:dns/py-bonjour \
	${PYTHON_PKGNAMEPREFIX}dnspython>0:dns/py-dnspython \
	${PYTHON_PKGNAMEPREFIX}requests>0:www/py-requests \
	${PYTHON_PKGNAMEPREFIX}openssl>0:security/py-openssl \
	${PYTHON_PKGNAMEPREFIX}pycrypto>0:security/py-pycrypto \
	${PYTHON_PKGNAMEPREFIX}simplejson>0:devel/py-simplejson \
	${PYTHON_PKGNAMEPREFIX}ujson>0:devel/py-ujson \
	${PYTHON_PKGNAMEPREFIX}oauth2>0:net/py-oauth2 \
	${PYTHON_PKGNAMEPREFIX}eventlet>0:net/py-eventlet \
	${PYTHON_PKGNAMEPREFIX}django-json-rpc>0:www/py-django-json-rpc \
	${PYTHON_PKGNAMEPREFIX}sqlparse>0:databases/py-sqlparse \
	${PYTHON_PKGNAMEPREFIX}licenselib>0:freenas/py-licenselib \
	${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd \
	${PYTHON_PKGNAMEPREFIX}middlewared>0:freenas/py-middlewared \
	${PYTHON_PKGNAMEPREFIX}rollbar>0:www/py-rollbar \
	${PYTHON_PKGNAMEPREFIX}ntplib>0:net/py-ntplib \
	pyvmomi>0:net/py-pyvmomi \
	dmidecode>0:sysutils/dmidecode \
	freenas-pkgtools>0:freenas/freenas-pkgtools \
	freenas-migrate93>0:freenas/freenas-migrate93

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

.if ${PRODUCT} == "TrueNAS"
RUN_DEPENDS+=	truenas-files>0:${PORTSDIR}/truenas/truenas-files
.endif

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
