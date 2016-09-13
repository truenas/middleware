# $FreeBSD: head/sysutils/nomad/Makefile 418616 2016-07-16 01:57:45Z kmoore $

PORTNAME=	nomad
PORTVERSION=	0.4.0
DISTVERSIONPREFIX=	v
PORTREVISION=	3
CATEGORIES=	sysutils

MAINTAINER=	john@pcbsd.org
COMMENT=	Cluster manager and scheduler

LICENSE=	MPL

BUILD_DEPENDS=	go>=1.4:lang/go
RUN_DEPENDS=	go>=1.4:lang/go

ONLY_FOR_ARCHS=	amd64

USES=	compiler

USE_GITHUB=	yes
GH_ACCOUNT=	hashicorp:DEFAULT kardianos:govendor mitchellh:gox \
		golang:tools axw:gocov matm:gocov_html ugorji:go
GH_PROJECT=	govendor:govendor gox:gox tools:tools gocov:gocov \
		gocov-html:gocov_html go:go
GH_TAGNAME=	36255b7:govendor 6e9ee79:gox 0d2bde8:tools \
		f5b2b5c:gocov b729399:gocov_html b94837a:go

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
