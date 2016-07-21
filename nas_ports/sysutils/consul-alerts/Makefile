# $FreeBSD$

PORTNAME=	consul-alerts
PORTVERSION=	0.3.3
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	john@pcbsd.org
COMMENT=	Simple daemon to send notifications based on Consul health checks

LICENSE=	GPLv2+

BUILD_DEPENDS=	${LOCALBASE}/bin/go:lang/go

USES=		compiler

USE_GITHUB=	yes
GH_ACCOUNT=	AcalephStorage
GH_TAGNAME=	v0.3.3

PLIST_FILES=	${PREFIX}/bin/consul-alerts

USE_RC_SUBR=	consul-alerts

STRIP=

post-patch:
	@${MKDIR} ${WRKSRC}/src/github.com/AcalephStorage/consul-alerts
.for src in .buildkite .buildkite-release .gitignore .travis.yml \
	check-handler.go consul consul-alerts.go Dockerfile \
	event-handler.go Godeps health-handler.go leader-election.go \
	LICENSE Makefile notifier provision README.md send-notifs.go \
	Vagrantfile watchers.go
	@${MV} ${WRKSRC}/${src} \
		${WRKSRC}/src/github.com/AcalephStorage/consul-alerts
.endfor

do-build:
	@cd ${WRKSRC}/src/github.com/AcalephStorage/consul-alerts; \
		${SETENV} ${BUILD_ENV} GOPATH=${WRKSRC} go build -v -x \
		-ldflags "-X main.GitDescribe=v${PORTVERSION}" -o bin/consul-alerts

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/AcalephStorage/consul-alerts/bin/consul-alerts ${STAGEDIR}${PREFIX}/bin/consul-alerts

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=	CC=clang
.endif

.include <bsd.port.post.mk>
