# $FreeBSD: head/sysutils/nomad/Makefile 426762 2016-11-21 22:02:30Z kmoore $

PORTNAME=	nomad
PORTVERSION=	0.5.0
PORTREVISION=	1
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	jhixson@gmail.com
COMMENT=	Cluster manager and scheduler

LICENSE=	MPL

BUILD_DEPENDS=	go>=1.7:lang/go

ONLY_FOR_ARCHS=	amd64

USES=	compiler

USE_GITHUB=	yes
GH_ACCOUNT=	hashicorp:DEFAULT kardianos:govendor mitchellh:gox \
		golang:tools axw:gocov matm:gocov_html ugorji:go
GH_PROJECT=	govendor:govendor gox:gox tools:tools gocov:gocov \
		gocov-html:gocov_html go:go
GH_TAGNAME=	v1.0.8:govendor v0.3.0:gox  8b84dae:tools \
		 c77561c:gocov v1.1:gocov_html faddd61:go

USE_RC_SUBR= nomad

USERS=	nomad
GROUPS=	nomad

STRIP=

post-patch:
	@${MKDIR} ${WRKSRC}/src/github.com/hashicorp/nomad
.for src in .gitignore .travis.yml api CHANGELOG.md client command \
	commands.go demo dist GNUmakefile helper ISSUE_TEMPLATE.md jobspec \
	LICENSE main_test.go main.go nomad README.md scheduler scripts \
	testutil Vagrantfile vendor version.go website
	@${MV} ${WRKSRC}/${src} \
		${WRKSRC}/src/github.com/hashicorp/nomad
.endfor
	@${MKDIR} ${WRKSRC}/src/github.com/axw
	@${MKDIR} ${WRKSRC}/src/github.com/kardianos
	@${MKDIR} ${WRKSRC}/src/github.com/matm
	@${MKDIR} ${WRKSRC}/src/github.com/mitchellh
	@${MKDIR} ${WRKSRC}/src/github.com/ugorji
	@${MKDIR} ${WRKSRC}/src/golang.org/x
	@${MKDIR} ${WRKSRC}/src/gopkg.in/matm/v1
	@${MV} ${WRKSRC_govendor} \
		${WRKSRC}/src/github.com/kardianos/govendor
	@${MV} ${WRKSRC_gox} \
		${WRKSRC}/src/github.com/mitchellh/gox
	@${MV} ${WRKSRC_gocov} \
		${WRKSRC}/src/github.com/axw/gocov
	@${MV} ${WRKSRC_go} \
		${WRKSRC}/src/github.com/ugorji/go
	@${MV} ${WRKSRC_gocov_html} \
		${WRKSRC}/src/gopkg.in/matm/v1/gocov-html
	@${MV} ${WRKSRC_tools} \
		${WRKSRC}/src/golang.org/x/tools

do-build:
	@cd ${WRKSRC}/src/github.com/hashicorp/nomad; \
	${SETENV} ${BUILD_ENV} GOPATH=${WRKSRC} go build -v -x \
		-ldflags "-X main.GitDescribe=v${PORTVERSION}" -o bin/nomad

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/hashicorp/nomad/bin/nomad ${STAGEDIR}${PREFIX}/bin/nomad
	${MKDIR} ${STAGEDIR}${PREFIX}/etc/nomad
	${INSTALL_DATA} ${WRKSRC}/src/github.com/hashicorp/nomad/dist/client.hcl \
		${STAGEDIR}${PREFIX}/etc/nomad/client.hcl.sample
	${INSTALL_DATA} ${WRKSRC}/src/github.com/hashicorp/nomad/dist/server.hcl \
		${STAGEDIR}${PREFIX}/etc/nomad/server.hcl.sample

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=  CC=clang
.endif

.include <bsd.port.post.mk>
