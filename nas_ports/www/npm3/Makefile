# Created by: Sunpoet Po-Chuan Hsieh <sunpoet@FreeBSD.org>
# $FreeBSD: head/www/npm3/Makefile 431486 2017-01-14 18:14:03Z sunpoet $

PORTNAME=	npm
PORTVERSION=	3.10.10
PORTREVISION=	1
CATEGORIES=	www
MASTER_SITES=	LOCAL/sunpoet
PKGNAMESUFFIX=	3

MAINTAINER=	sunpoet@FreeBSD.org
COMMENT=	Node package manager

LICENSE=	MIT

RUN_DEPENDS=	gmake:devel/gmake

CONFLICTS_INSTALL=	npm- npm2-

OPTIONS_SINGLE=	BACKEND
OPTIONS_SINGLE_BACKEND=	NODE NODE6
OPTIONS_DEFAULT=NODE6
NODE_DESC=	Use www/node as backend
NODE6_DESC=	Use www/node6 as backend

MAKE_ARGS=	npm_config_prefix=${STAGEDIR}${PREFIX}
MANPREFIX=	${PREFIX}/lib/node_modules/npm
NO_ARCH=	yes
NO_BUILD=	yes
REINPLACE_ARGS=	-i ''
USES=		cpe python:2 shebangfix tar:xz

CPE_VENDOR=	npmjs
CPE_PRODUCT=	node_packaged_modules

SHEBANG_FILES=	lib/utils/completion.sh \
		node_modules/node-gyp/test/docker.sh \
		node_modules/request/node_modules/node-uuid/benchmark/bench.sh \
		scripts/clean-old.sh \
		scripts/release.sh \
		scripts/relocate.sh

NODE_RUN_DEPENDS=	node>=0.8.0:www/node
NODE6_RUN_DEPENDS=	node6>=0.8.0:www/node6

.include <bsd.port.pre.mk>

.if ${ARCH} == "i386"
# Workaround for kernel bug 178881
EXTRA_PATCHES+=	${PATCHDIR}/extra-patch-bug-178881
.endif

post-patch:
	@${REINPLACE_CMD} -e 's|node cli.js|& --cache ${WRKDIR}/.cache|' ${WRKSRC}/Makefile
	@${ECHO_CMD} 'MANPATH ${PREFIX}/lib/node_modules/npm/man' > ${WRKDIR}/npm.conf
	@${REINPLACE_CMD} -e 's|exec python|exec ${PYTHON_CMD}|' ${WRKSRC}/node_modules/node-gyp/gyp/gyp

post-install:
	${INSTALL_DATA} ${WRKDIR}/npm.conf ${STAGEDIR}${PREFIX}/etc/man.d/npm.conf

.include <bsd.port.post.mk>
