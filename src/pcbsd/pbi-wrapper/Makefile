SRCS=pbiwrapper.c
BINDIR=/usr/pbi
NO_MAN=

.if ${MACHINE_CPUARCH} == "amd64"
PROG=.pbiwrapper-amd64
.elif ${MACHINE_CPUARCH} == "i386"
PROG=.pbiwrapper-i386
.endif

.include <bsd.prog.mk>
