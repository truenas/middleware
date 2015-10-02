.include <bsd.own.mk>

.include "Makefile.inc"

SUBDIR= create_manifest \
	create_package \
	diff_packages \
	freenas-install \
	lib \
	manifest_util \
	pkgify \
	freenas-update \
	freenas-release \
	freenas-verify \
	verify_signature \
	certificates

beforeinstall:
	${INSTALL} -d ${DESTDIR}${BINDIR}
	${INSTALL} -d ${DESTDIR}${LIBDIR}

.include <bsd.subdir.mk>

# Any similarity to a port Makefile is coincidental.
PORTNAME=	freenas-pkgtools
.if !defined(REVISION)
REVISION!=	git rev-parse --short HEAD
.endif

.if ${REVISION} == ""
REVISION=	1
.endif

PYTHON_PKGNAMEPREFIX=	py27-
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}openssl \
		${PYTHON_PKGNAMEPREFIX}sqlite3 \
		python \
		python2 \
		python27

.ORDER:	install package

ROOTDIR= ${DESTDIR}${BINDIR:S/usr\/local\/bin//}

.if !defined(PACKAGE_DIR)
PACKAGE_DIR=	/tmp/Packages
.endif

# This creates a package to be installed
# on the update server.  This is a slightly
# different set of files than are installed on
# FreeNAS itself.

# There's got to be a better way to do this.
package: install
	mkdir -p ${PACKAGE_DIR}
	( echo ' { '; for dep in ${RUN_DEPENDS}; do \
		pkg query "	\"%n\" : { \"origin\" : \"%o\", \"version\" : \"%v\" }," $$dep; \
		done ; echo '}' ) | \
		python -c 'import os, sys, json; m = json.load(open(sys.argv[1])); \
			m["version"] = "'${REVISION}'"; d = eval(sys.stdin.read()); \
			m["deps"] = d; \
			json.dump(m, sys.stdout, sort_keys=True, indent=4, separators=(",", ": "));' \
				${.CURDIR}/files/+MANIFEST \
			> ${.OBJDIR}/+MANIFEST
	/usr/sbin/pkg create -o ${PACKAGE_DIR} -p ${.CURDIR}/files/pkg-plist -r ${ROOTDIR} -m ${.OBJDIR} -f tgz

