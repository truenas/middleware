# $FreeBSD$

PORTNAME=	freenas-installer
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	FreeNAS installer

USE_XZ=		yes

PREFIX=/

# explicitly set this for the port build
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/nas_source

# no checksum, we just used git!
checksum fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

do-build:
	:

do-install:
	mkdir -p ${STAGEDIR}/${PREFIX}/pre-install
	${INSTALL_SCRIPT} ${WRKSRC}/build/nanobsd-cfg/Installer/bin/install_worker.sh ${STAGEDIR}/${PREFIX}/bin/install_worker.sh
	${INSTALL_SCRIPT} ${WRKSRC}/build/nanobsd-cfg/Installer/bin/install_worker2.sh ${STAGEDIR}/${PREFIX}/bin/install_worker2.sh
	${INSTALL_SCRIPT} ${WRKSRC}/build/files/install.sh ${STAGEDIR}/${PREFIX}/etc/install.sh
	${INSTALL_SCRIPT} ${WRKSRC}/build/files/rc ${STAGEDIR}/${PREFIX}/etc/rc
	${INSTALL_SCRIPT} ${WRKSRC}/build/nanobsd-cfg/Installer/lib/functions.sh ${STAGEDIR}/${PREFIX}/lib/functions.sh
	cp -a ${WRKSRC}/build/nanobsd-cfg/Installer/pre-install/ ${STAGEDIR}/${PREFIX}/pre-install/

.include <bsd.port.mk>
