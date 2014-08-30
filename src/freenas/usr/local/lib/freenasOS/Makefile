BINDIR=	/usr/local/lib/freenasOS

.include <bsd.own.mk>

SCRIPTS=	Configuration.py Manifest.py Package.py Exceptions.py __init__.py
SCRIPTSNAME=
SCRIPTSMODE=	0444

.for script in ${SCRIPTS}
SCRIPTSNAME_${script:T}=${script}
.endfor

beforeinstall:
	-${INSTALL} ${INSTALLFLAGS} -d -o ${BINOWN} -g ${BINGRP} ${DESTDIR}${BINDIR}

.include <bsd.prog.mk>

