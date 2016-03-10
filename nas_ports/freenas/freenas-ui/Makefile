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

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}django16>0:${PORTSDIR}/www/py-django16 \
	${PYTHON_PKGNAMEPREFIX}south>0:${PORTSDIR}/databases/py-south \
	${PYTHON_PKGNAMEPREFIX}django-tastypie>0:${PORTSDIR}/www/py-django-tastypie \
	${PYTHON_PKGNAMEPREFIX}lockfile>0:${PORTSDIR}/devel/py-lockfile \
	${PYTHON_PKGNAMEPREFIX}ipaddr>0:${PORTSDIR}/devel/py-ipaddr \
	${PYTHON_PKGNAMEPREFIX}bsddb3>0:${PORTSDIR}/databases/py-bsddb3 \
	${PYTHON_PKGNAMEPREFIX}libxml2>0:${PORTSDIR}/textproc/py-libxml2 \
	${PYTHON_PKGNAMEPREFIX}polib>0:${PORTSDIR}/devel/py-polib \
	${PYTHON_PKGNAMEPREFIX}ldap>0:${PORTSDIR}/net/py-ldap \
	${PYTHON_PKGNAMEPREFIX}dojango>0:${PORTSDIR}/www/py-dojango \
	${PYTHON_PKGNAMEPREFIX}sysctl>0:${PORTSDIR}/devel/py-sysctl \
	${PYTHON_PKGNAMEPREFIX}lxml>0:${PORTSDIR}/devel/py-lxml \
	${PYTHON_PKGNAMEPREFIX}pybonjour>0:${PORTSDIR}/dns/py-bonjour \
	${PYTHON_PKGNAMEPREFIX}dnspython>0:${PORTSDIR}/dns/py-dnspython \
	${PYTHON_PKGNAMEPREFIX}requests>0:${PORTSDIR}/www/py-requests \
	${PYTHON_PKGNAMEPREFIX}openssl>0:${PORTSDIR}/security/py-openssl \
	${PYTHON_PKGNAMEPREFIX}pycrypto>0:${PORTSDIR}/security/py-pycrypto \
	${PYTHON_PKGNAMEPREFIX}simplejson>0:${PORTSDIR}/devel/py-simplejson \
	${PYTHON_PKGNAMEPREFIX}sqlparse>0:${PORTSDIR}/databases/py-sqlparse \
	${PYTHON_PKGNAMEPREFIX}licenselib>0:${PORTSDIR}/freenas/py-licenselib \
	dmidecode>0:${PORTSDIR}/sysutils/dmidecode

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

do-install:
	${RM} -f ${PLIST}
	${ECHO_CMD} "@owner www"  >> ${TMPPLIST}
	${ECHO_CMD} "@group www"  >> ${TMPPLIST}
	${MKDIR} ${STAGEDIR}${PREFIX}/www/freenasUI
	${CP} -a ${WRKSRC}/ ${STAGEDIR}${PREFIX}/www/freenasUI
.if ${PRODUCT} == "TrueNAS"
	${CP} -a /usr/truenas/gui/ ${STAGEDIR}${PREFIX}/www/freenasUI
.endif
	${LN} -s -f /etc/local_settings.py ${STAGEDIR}${PREFIX}/www/freenasUI/local_settings.py
	(cd ${STAGEDIR}${PREFIX}; ${FIND} . \( -type f -o -type l \) \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "www/freenasUI/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
