# $FreeBSD$
# $Id$
#
PORTNAME=	snmp_passpersist
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas net-mgmt

MAINTAINER=     dev@ixsystems.com
COMMENT=	Python client library for Net-SNMP pass persist backend

LICENSE=	GPLv3

RUN_DEPENDS=	net-snmp>=0:${PORTSDIR}/net-mgmt/net-snmp

USES=			python
USE_PYTHON=	distutils autoplist
EXTRACT_ONLY=


WRKSRC=		/usr/nas_source/py-snmp_passpersist

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
