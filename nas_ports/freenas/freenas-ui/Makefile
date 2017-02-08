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

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}django110>0:${PORTSDIR}/www/py-django110 \
	samba45>0:${PORTSDIR}/net/samba45 \
	uwsgi>0:${PORTSDIR}/www/uwsgi \
	${PYTHON_PKGNAMEPREFIX}django-formtools>0:${PORTSDIR}/www/py-django-formtools \
	${PYTHON_PKGNAMEPREFIX}django-tastypie>0:${PORTSDIR}/www/py-django-tastypie \
	${PYTHON_PKGNAMEPREFIX}lockfile>0:${PORTSDIR}/devel/py-lockfile \
	${PYTHON_PKGNAMEPREFIX}ipaddr>0:${PORTSDIR}/devel/py-ipaddr \
	${PYTHON_PKGNAMEPREFIX}bsddb3>0:${PORTSDIR}/databases/py-bsddb3 \
	${PYTHON_PKGNAMEPREFIX}libxml2>0:${PORTSDIR}/textproc/py-libxml2 \
	${PYTHON_PKGNAMEPREFIX}polib>0:${PORTSDIR}/devel/py-polib \
	${PYTHON_PKGNAMEPREFIX}pyldap>0:${PORTSDIR}/net/py-pyldap \
	${PYTHON_PKGNAMEPREFIX}dojango>0:${PORTSDIR}/www/py-dojango \
	${PYTHON_PKGNAMEPREFIX}sysctl>0:${PORTSDIR}/devel/py-sysctl \
	${PYTHON_PKGNAMEPREFIX}lxml>0:${PORTSDIR}/devel/py-lxml \
	${PYTHON_PKGNAMEPREFIX}pybonjour>0:${PORTSDIR}/dns/py-bonjour \
	${PYTHON_PKGNAMEPREFIX}dnspython>0:${PORTSDIR}/dns/py-dnspython \
	${PYTHON_PKGNAMEPREFIX}requests>0:${PORTSDIR}/www/py-requests \
	${PYTHON_PKGNAMEPREFIX}openssl>0:${PORTSDIR}/security/py-openssl \
	${PYTHON_PKGNAMEPREFIX}pycrypto>0:${PORTSDIR}/security/py-pycrypto \
	${PYTHON_PKGNAMEPREFIX}simplejson>0:${PORTSDIR}/devel/py-simplejson \
	${PYTHON_PKGNAMEPREFIX}ujson>0:${PORTSDIR}/devel/py-ujson \
	${PYTHON_PKGNAMEPREFIX}oauth2>0:${PORTSDIR}/net/py-oauth2 \
	${PYTHON_PKGNAMEPREFIX}eventlet>0:${PORTSDIR}/net/py-eventlet \
	${PYTHON_PKGNAMEPREFIX}django-json-rpc>0:${PORTSDIR}/www/py-django-json-rpc \
	${PYTHON_PKGNAMEPREFIX}sqlparse>0:${PORTSDIR}/databases/py-sqlparse \
	${PYTHON_PKGNAMEPREFIX}licenselib>0:${PORTSDIR}/freenas/py-licenselib \
	${PYTHON_PKGNAMEPREFIX}bsd>0:${PORTSDIR}/freenas/py-bsd \
	${PYTHON_PKGNAMEPREFIX}middlewared>0:${PORTSDIR}/freenas/py-middlewared \
	${PYTHON_PKGNAMEPREFIX}rollbar>0:${PORTSDIR}/www/py-rollbar \
	${PYTHON_PKGNAMEPREFIX}pysphere-freenas>0:${PORTSDIR}/net/py-pysphere-freenas \
	pyvmomi>0:${PORTSDIR}/net/py-pyvmomi \
	dmidecode>0:${PORTSDIR}/sysutils/dmidecode \
	freenas-pkgtools>0:${PORTSDIR}/freenas/freenas-pkgtools \
	freenas-migrate93>0:${PORTSDIR}/freenas/freenas-migrate93 \
	${PYTHON_PKGNAMEPREFIX}ntplib>0:${PORTSDIR}/net/py-ntplib

EXTRACT_ONLY=
WRKSRC=/usr/freenasUI

NO_BUILD=yes

PLIST=		${WRKDIR}/plist

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

pre-install:
	${RM} -f ${PLIST}
	${ECHO_CMD} "@owner www"  >> ${PLIST}
	${ECHO_CMD} "@group www"  >> ${PLIST}
	${ECHO_CMD} "@comment files" >> ${PLIST}
	${FIND} ${WRKSRC} -type f | \
		${SED} -e 's|^/usr/|/www/|' -e 's|^/||' \
		| ${SORT} >> ${PLIST}
	${ECHO_CMD} www/freenasUI/local_settings.py >> ${PLIST}
	${ECHO_CMD} "@comment directories" >> ${PLIST}
	${FIND} ${WRKSRC} -type d \
		| ${SED} -e 's|^/usr/|/www/|' -e 's|^/||' -e 's|^|@dirrm |' \
		| ${SORT} -r >> ${PLIST}

do-install:
	${RM} -fr ${STAGEDIR}${PREFIX}/www/freenasUI
	${MKDIR} ${STAGEDIR}${PREFIX}/www/freenasUI
	${CP} -a ${WRKSRC}/ ${STAGEDIR}${PREFIX}/www/freenasUI
	${LN} -s -f /etc/local_settings.py ${STAGEDIR}${PREFIX}/www/freenasUI/local_settings.py

.include <bsd.port.post.mk>
