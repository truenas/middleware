.include <bsd.own.mk>

#BINDIR=	${PREFIX}/lib/freenasOS
#LIBDIR= ${PREFIX}/lib/freenasOS

FILESDIR= ${LIBDIR}

FILES=	Configuration.py \
	Exceptions.py \
	Installer.py \
	Manifest.py \
	Package.py \
	Train.py \
	__init__.py

beforeinstall:
	echo "BINDIR = ${BINDIR}, LIBDIR = ${LIBDIR}"

.include <bsd.lib.mk>

