# Created by: Mario Sergio Fujikawa Ferreira <lioux@FreeBSD.org>
# $FreeBSD$

PORTNAME=	dnspython
PORTVERSION=	1.12.0
CATEGORIES=	dns python
MASTER_SITES=	http://www.dnspython.org/kits${PORTVERSIONSUFFIX}/${PORTVERSION}/
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}
PKGNAMESUFFIX=	2
DISTNAME=	${PORTNAME}${PORTVERSIONSUFFIX}-${PORTVERSION}

MAINTAINER=	rm@FreeBSD.org
COMMENT=	DNS toolkit for Python

USES=		python:2
USE_PYTHON=	autoplist distutils

OPTIONS_DEFINE=	DOCS EXAMPLES PYCRYPTO
PYCRYPTO_DESC=	Enable pycrypto (part of dnssec needs it)

PORTDOCS=	ChangeLog README
DOCSDIR=	${PREFIX}/share/doc/${PYTHON_PKGNAMEPREFIX}${PORTNAME}

PORTEXAMPLES=	ddns.py e164.py mx.py name.py reverse.py reverse_name.py \
		xfr.py zonediff.py
EXAMPLESDIR=	${PREFIX}/share/examples/${PYTHON_PKGNAMEPREFIX}${PORTNAME}

PYCRYPTO_RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}pycrypto>0:${PORTSDIR}/security/py-pycrypto

.include <bsd.port.pre.mk>

.if ${PYTHON_MAJOR_VER} < 3
PORTVERSIONSUFFIX=
.else
PORTVERSIONSUFFIX=	3
EXAMPLESDIR:=	${EXAMPLESDIR}3
.endif

post-install:
# docs
	@${MKDIR} ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${PORTDOCS:S,^,${WRKSRC}/,} ${STAGEDIR}${DOCSDIR}
# examples
	@${MKDIR} ${STAGEDIR}${EXAMPLESDIR}
	${INSTALL_DATA} ${PORTEXAMPLES:S,^,${WRKSRC}/examples/,} ${STAGEDIR}${EXAMPLESDIR}
# permission safeness
	@${FIND} ${STAGEDIR}${PYTHONPREFIX_SITELIBDIR}/dns -type f -exec ${CHMOD} ${SHAREMODE} {} \;
	@${FIND} ${STAGEDIR}${PYTHONPREFIX_SITELIBDIR}/dns -type d -exec ${CHMOD} 755 {} \;

.include <bsd.port.post.mk>
