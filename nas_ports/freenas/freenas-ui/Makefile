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

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}django110>0:www/py-django110@${PY_FLAVOR} \
	uwsgi>0:www/uwsgi \
	${PYTHON_PKGNAMEPREFIX}django-formtools>0:www/py-django-formtools@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}django-tastypie>0:www/py-django-tastypie@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}lockfile>0:devel/py-lockfile@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}ipaddr>0:devel/py-ipaddr@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}bsddb3>0:databases/py-bsddb3@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}polib>0:devel/py-polib@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}ldap>0:net/py-ldap@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}dojango>0:www/py-dojango@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}sysctl>0:devel/py-sysctl@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}lxml>0:devel/py-lxml@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}pybonjour>0:dns/py-bonjour@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}dnspython>0:dns/py-dnspython@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}requests>0:www/py-requests@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}requests-toolbelt>0:www/py-requests-toolbelt@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}openssl>0:security/py-openssl@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}pycryptodome>0:security/py-pycryptodome@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}simplejson>0:devel/py-simplejson@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}ujson>0:devel/py-ujson@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}oauth2>0:net/py-oauth2@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}django-json-rpc>0:www/py-django-json-rpc@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}sqlparse>0:databases/py-sqlparse@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}licenselib>0:freenas/py-licenselib@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}middlewared>0:freenas/py-middlewared@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}ntplib>0:net/py-ntplib@${PY_FLAVOR} \
	${PYTHON_PKGNAMEPREFIX}snmp4>0:net-mgmt/py-snmp4@${PY_FLAVOR} \
	pyvmomi>0:net/py-pyvmomi \
	dmidecode>0:sysutils/dmidecode \
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
