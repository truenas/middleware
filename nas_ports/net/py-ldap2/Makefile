# $FreeBSD$

PORTNAME=	ldap2
PORTVERSION=	2.4.19
CATEGORIES=	net python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}
DISTNAME=	python-ldap-${PORTVERSION}

MAINTAINER=	rm@FreeBSD.org
COMMENT=	LDAP module for python, for OpenLDAP2

LICENSE=	PSFL
LICENSE_FILE=	${WRKSRC}/LICENCE

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}asn1-modules>=0:${PORTSDIR}/devel/py-asn1-modules

USES=		python:2
USE_PYTHON=	autoplist distutils
USE_OPENLDAP=		yes
WANT_OPENLDAP_VER=	24

REPLACE_ARGS=	-e 's,/opt/openldap-RE24/lib,${LOCALBASE}/lib,' \
		-e 's,/opt/openldap-RE24/include,${LOCALBASE}/include,' \
		-e 's,/usr/include/sasl,${LOCALBASE}/include/sasl,'

OPTIONS_DEFINE=	SASL

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MSASL}
WANT_OPENLDAP_SASL=	yes
CONFLICTS+=		openldap2[34]-client-2.*
.endif

do-configure:
	@${REINPLACE_CMD} ${REPLACE_ARGS} ${WRKSRC}/setup.cfg
.if ! ${PORT_OPTIONS:MSASL}
	@cd ${WRKSRC} && ${PYTHON_CMD} setup.py -q setopt -c _ldap -s HAVE_TLS -o defines
	@cd ${WRKSRC} && ${PYTHON_CMD} setup.py -q saveopts
.endif

.include <bsd.port.mk>
