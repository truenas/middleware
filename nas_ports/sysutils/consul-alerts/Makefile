# $FreeBSD: head/sysutils/consul-alerts/Makefile 418851 2016-07-20 19:56:26Z kmoore $

PORTNAME=	consul-alerts
PORTVERSION=	0.4.0
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	jhixson@gmail.com
COMMENT=	Simple daemon to send notifications based on Consul health checks

LICENSE=	GPLv2+

BUILD_DEPENDS=	${LOCALBASE}/bin/go:lang/go

USES=		compiler

USE_GITHUB=	yes
GH_ACCOUNT=	AcalephStorage aws:aws_sdk_go
GH_PROJECT=	aws-sdk-go:aws_sdk_go
GH_TAGNAME=	v1.5.12:aws_sdk_go
GH_SUBDIR=	src/github.com/${GH_ACCOUNT}/${PORTNAME}

PLIST_FILES=	${PREFIX}/bin/consul-alerts

USE_RC_SUBR=	consul-alerts

STRIP=

post-patch:
	@${MKDIR} ${WRKDIR}/src/github.com/AcalephStorage
	@${MV} ${WRKSRC} \
		${WRKDIR}/src/github.com/AcalephStorage/consul-alerts
	@${MKDIR} ${WRKDIR}/src/github.com/aws
	@${MV} ${WRKSRC_aws_sdk_go} \
		${WRKDIR}/src/github.com/aws/aws-sdk-go

do-build:
	@cd ${WRKDIR}/src/github.com/AcalephStorage/consul-alerts; \
		${SETENV} ${BUILD_ENV} GOPATH=${WRKDIR} go build -v -x \
		-ldflags "-X main.GitDescribe=v${PORTVERSION}" -o bin/consul-alerts

do-install:
	${INSTALL_PROGRAM} ${WRKDIR}/src/github.com/AcalephStorage/consul-alerts/bin/consul-alerts ${STAGEDIR}${PREFIX}/bin/consul-alerts

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=	CC=clang
.endif

.include <bsd.port.post.mk>
