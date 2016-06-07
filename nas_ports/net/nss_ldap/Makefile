# Created by: Jacques Vidrine <nectar@FreeBSD.org>
# $FreeBSD$

PORTNAME=	nss_ldap
PORTVERSION=	1.${NSS_LDAP_VERSION}
PORTREVISION=	12
CATEGORIES=	net
MASTER_SITES=	http://www.padl.com/download/ \
		LOCAL/martymac
DISTNAME=	${PORTNAME}-${NSS_LDAP_VERSION}

MAINTAINER=	des@FreeBSD.org
COMMENT=	RFC 2307 NSS module

LICENSE=	GPLv2

NSS_LDAP_VERSION=265

USES=		autoreconf gmake perl5
USE_PERL5=	build
GNU_CONFIGURE=	yes
USE_LDCONFIG=	yes
USE_OPENLDAP=	yes

OPTIONS_DEFINE=	LCLASS KERBEROS SASL
OPTIONS_DEFAULT=LCLASS KERBEROS

LCLASS_DESC=	Enable login classes via the loginClass attribute

SASL_DESC=	Use the SASL-enabled version of OpenLDAP

CPPFLAGS+=	-I${LOCALBASE}/include
LDFLAGS+=	-L${LOCALBASE}/lib -Wl,-rpath,${LOCALBASE}/lib

CONFIGURE_ARGS=	--with-ldap-conf-file=${PREFIX}/etc/nss_ldap.conf \
		--with-ldap-secret-file=${PREFIX}/etc/nss_ldap.secret \
		--enable-rfc2307bis \
		--enable-paged-results

SUB_FILES=	pkg-message

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MKERBEROS}
CONFIGURE_ARGS+=--enable-configurable-krb5-ccname-gssapi \
		--enable-configurable-krb5-keytab
.endif

.if ${PORT_OPTIONS:MLCLASS}
CFLAGS+="-DHAVE_LOGIN_CLASSES"
.endif

.if ${PORT_OPTIONS:MSASL}
WANT_OPENLDAP_SASL=	 yes
.endif

post-extract:
	${CP} ${FILESDIR}/bsdnss.c ${WRKSRC}

post-patch:
	@${REINPLACE_CMD} -e 's,/etc/ldap\.,${PREFIX}/etc/nss_ldap.,g' \
		-e 's,/etc/openldap/ldap\.,${PREFIX}/etc/openldap/ldap.,g' \
		${WRKSRC}/ldap.conf
	@${REINPLACE_CMD} 's,#!/usr/bin/perl,#!${PERL},' \
		${WRKSRC}/vers_string
	@${REINPLACE_CMD} 's,/etc/ldap\.,${PREFIX}/etc/nss_ldap.,g' \
		${WRKSRC}/nss_ldap.5

# XXX: newer autoconf's rely on the compiler result, not the preprocessor
#      for checking headers, so the configure.in needs to be fixed upstream
#      to properly include dependencies
post-configure:
	@${ECHO} "#define HAVE_NETINET_IF_ETHER_H 1" >> ${WRKSRC}/config.h
	@${ECHO} "#define HAVE_NET_ROUTE_H 1" >> ${WRKSRC}/config.h
	@${ECHO} "#define HAVE_RESOLV_H 1" >> ${WRKSRC}/config.h

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/nss_ldap.so ${STAGEDIR}/${PREFIX}/lib/nss_ldap.so.1
	${INSTALL_DATA} ${WRKSRC}/ldap.conf ${STAGEDIR}/${PREFIX}/etc/nss_ldap.conf.sample
	${INSTALL_MAN} ${WRKSRC}/nss_ldap.5 ${STAGEDIR}/${MAN5PREFIX}/man/man5

.include <bsd.port.mk>
