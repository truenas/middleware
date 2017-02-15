# $FreeBSD: head/sysutils/nomad/Makefile 434121 2017-02-14 16:06:10Z amdmi3 $

PORTNAME=	nomad
PORTVERSION=	0.5.4
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	jhixson@gmail.com
COMMENT=	Cluster manager and scheduler

LICENSE=	MPL

BUILD_DEPENDS=	go>=1.7:lang/go

ONLY_FOR_ARCHS=	amd64

USES=		compiler

USE_GITHUB=	yes
GH_ACCOUNT=	hashicorp
GH_SUBDIR=	src/github.com/hashicorp/nomad
GH_TUPLE=	kardianos:govendor:v1.0.8:govendor/src/github.com/kardianos/govendor \
		mitchellh:gox:v0.3.0:gox/src/github.com/mitchellh/gox \
		golang:tools:8b84dae:tools/src/golang.org/x/tools \
		axw:gocov:c77561c:gocov/src/github.com/axw/gocov \
		matm:gocov-html:v1.1:gocov_html/src/gopkg.in/matm/v1/gocov-html \
		ugorji:go:faddd61:go/src/github.com/ugorji/go


USE_RC_SUBR=	nomad

USERS=		nomad
GROUPS=		nomad

STRIP=

do-build:
	@cd ${WRKSRC}/src/github.com/hashicorp/nomad; \
	${SETENV} ${BUILD_ENV} GOPATH=${WRKSRC} go build -v -x \
		-ldflags "-X main.GitDescribe=v${PORTVERSION}" -o bin/nomad

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/hashicorp/nomad/bin/nomad ${STAGEDIR}${PREFIX}/bin/nomad
	@${MKDIR} ${STAGEDIR}${PREFIX}/etc/nomad
	${INSTALL_DATA} ${WRKSRC}/src/github.com/hashicorp/nomad/dist/client.hcl \
		${STAGEDIR}${PREFIX}/etc/nomad/client.hcl.sample
	${INSTALL_DATA} ${WRKSRC}/src/github.com/hashicorp/nomad/dist/server.hcl \
		${STAGEDIR}${PREFIX}/etc/nomad/server.hcl.sample

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=  CC=clang
.endif

.include <bsd.port.post.mk>
